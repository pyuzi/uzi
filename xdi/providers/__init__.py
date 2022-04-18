import sys
from types import GenericAlias
import typing as t
from collections import abc
from functools import partial, wraps
from inspect import (Parameter, Signature, iscoroutinefunction)
from logging import getLogger

from typing_extensions import Self

import attr

from xdi._common import lazy

from .. import (Dep, Injectable, InjectionMarker, Provided, PureDep, T_Injectable, T_Injected,
                is_injectable, _dependency as dependency)
from .._common import Missing, private_setattr, typed_signature, frozendict
from .._functools import BoundParams



if sys.version_info < (3, 10):  # pragma: py-gt-39
    _UnionType = type(t.Union[t.Any, None])
else:                           # pragma: py-lt-310
    from types import UnionType as _UnionType

_AnnotatedType = type(t.Annotated[t.Any, 'ann'])



if t.TYPE_CHECKING:  # pragma: no cover
    from ..containers import Container
    from ..scopes import Injector, Scope




logger = getLogger(__name__)


_T = t.TypeVar("_T")
_T_Fn = t.TypeVar("_T_Fn", bound=abc.Callable, covariant=True)
_T_Concrete = t.TypeVar("_T_Concrete")

_T_Dep = t.TypeVar('_T_Dep', bound=dependency.Dependency, covariant=True)



def _fluent_decorator(fn=None,  default=Missing, *, fluent: bool = False):
    def decorator(func: _T_Fn) -> _T_Fn:
        @wraps(func)
        def wrapper(self, v=default, /, *args, **kwds):
            nonlocal func, default, fluent
            if v is default:
                def decorator(val: _T) -> _T:
                    nonlocal func, v, args, kwds
                    rv = func(self, val, *args, **kwds)
                    return rv if fluent is True else val
                return decorator
            return func(self, v, *args, **kwds)

        wrapper._is_fluent_decorator = True

        return wrapper

    return decorator if fn is None else decorator(fn)






@private_setattr(frozen='_frozen')
@attr.s(slots=True, frozen=True, eq=False)
class Provider(t.Generic[_T_Concrete, _T_Dep]):

    _frozen: bool = attr.ib(init=False, default=False)

    concrete: _T_Concrete = attr.ib(default=Missing)
    """The object used to resolve 
    """

    container: "Container" = attr.ib(kw_only=True, default=None) 
    """The Container where this provider is setup.
    """

    is_default: bool = attr.ib(kw_only=True, default=False)
    """Whether this provider is the default. 
    A default provider only gets used if none other was provided to override it.
    """

    is_async: bool = attr.ib(init=False, default=None)
    """Whether this provider is final. Final providers cannot be overridden 
    """

    filters: tuple[abc.Callable[['Scope', Injectable], bool]] = attr.ib(kw_only=True, default=(), converter=tuple)
    """Called to determine whether this provider can be bound.
    """

    _dependency_class: t.ClassVar[type[_T_Dep]] = None
    _dependency_kwargs: t.ClassVar = {}

    __class_getitem__ = classmethod(GenericAlias)

    def set_container(self, container: "Container") -> Self:
        if not self.container is None:
            if not container is self.container:
                raise AttributeError(
                    f"container for `{self}` already set to `{self.container}`."
                )
        else:
            self.__setattr(container=container)
        return self
   
    def when(self, *filters, replace: bool=False) -> Self:
        if replace:
            self.__setattr(filters=tuple(dict.fromkeys(filters)))
        else:
            self.__setattr(filters=tuple(dict.fromkeys(self.filters + filters)))
        return self

    def default(self, is_default: bool = True) -> Self:
        self.__setattr(is_default=is_default)
        return self

    @t.overload
    def use(self) -> abc.Callable[[_T], _T]: ...
    @t.overload
    def use(self, using: t.Any) -> Self: ...
    @_fluent_decorator()
    def use(self, using):
        self.__setattr(concrete=using)
        return self

    def can_resolve(self, abstract: T_Injectable, scope: "Scope") -> bool:
        return (not (container := self.container) or container in scope) \
            and self._can_resolve(abstract, scope) \
            and self._apply_filters(abstract, scope)

    def _can_resolve(self, abstract: T_Injectable, scope: "Scope") -> bool:
        return True

    def _apply_filters(self, abstract: T_Injectable, scope: "Scope") -> bool:
        for fl in self.filters:
            if not fl(self, abstract, scope):
                return False
        return True

    def resolve(self, abstract: T_Injectable, scope: 'Scope'):
        self._freeze()
        if self.can_resolve(abstract, scope):
            return self._resolve(abstract, scope)

    def _resolve(self, abstract: T_Injectable, scope: 'Scope') -> dependency.Dependency:
        return self._make_dependency(abstract, scope)

    def _freeze(self):
        self._frozen or (self._onfreeze(), self.__setattr(_frozen=True))

    def _onfreeze(self):
        ...

    def _get_dependency_kwargs(self, **kwds):
        return self._dependency_kwargs | kwds

    def _make_dependency(self, abstract: T_Injectable, scope: 'Scope', **kwds):
        if cls := self._dependency_class:
            return cls(abstract, scope, self, **self._get_dependency_kwargs(**kwds))
        raise NotImplementedError(f'{self.__class__.__name__}._make_dependency()') # pragma: no cover

    def __eq__(self, x):
        return x is self

    def __hash__(self):
        return id(self)





@attr.s(slots=True, frozen=True, cmp=False)
class Value(Provider[_T_Concrete, dependency.Value]):
    """Provides given value as it is."""

    _dependency_class = dependency.Value

    def _get_dependency_kwargs(self, **kwds):
        kwds.setdefault('concrete', self.concrete)
        return super()._get_dependency_kwargs(**kwds)




@attr.s(slots=True, frozen=True, cmp=False)
class Alias(Provider[_T_Concrete]):

    def _resolve(self, abstract: T_Injectable, scope: 'Scope'):
        return scope[self.concrete]
  
  

@attr.s(slots=True, frozen=True, cmp=False)
class UnionProvider(Provider[_T_Concrete]):

    abstract = t.get_origin(t.Union[t.Any, None])
    concrete = attr.ib(init=False, default=_UnionType)

    def get_all_args(self, abstract: Injectable):
        return t.get_args(abstract)

    def get_injectable_args(self, abstract: Injectable):
        return filter(is_injectable, self.get_all_args(abstract))

    def _resolve(self, abstract: T_Injectable, scope: 'Scope'):
        logger.error(f'{abstract=}')
        logger.error(f'{self.concrete=}')
        for arg in self.get_injectable_args(abstract):
            if rv := scope[arg]:
                return rv

    def _can_resolve(self, abstract: T_Injectable, scope: "Scope") -> bool:
        return isinstance(abstract, self.concrete)



@attr.s(slots=True, frozen=True, cmp=False)
class AnnotatedProvider(UnionProvider[_T_Concrete]):

    abstract = t.get_origin(t.Annotated[t.Any, None])
    concrete = attr.ib(init=False, default=_AnnotatedType)

    def get_all_args(self, abstract: t.Annotated):
        for a in abstract.__metadata__[::-1]:
            if isinstance(a, InjectionMarker):
                yield a
        yield abstract.__origin__

  



@attr.s(slots=True, frozen=True, cmp=False)
class DepMarkerProvider(Provider[_T_Concrete]):
    
    abstract = Dep
    concrete = attr.ib(init=False, default=Dep)
    _dependency_class = dependency.Value

    def _can_resolve(self, abstract: T_Injectable, scope: "Scope") -> bool:
        return isinstance(abstract, (self.concrete, Dep, PureDep))

    def _resolve(self, marker: Dep, scope: 'Scope') -> dependency.Dependency:
        abstract, where = marker.abstract, marker.scope

        if where == Dep.SKIP_SELF:
            if dep := scope.find_remote(abstract):
                return dep
        elif where == Dep.ONLY_SELF:
            dep = scope.find_local(abstract)
            if dep and scope is dep.scope:
                return dep
        elif dep := scope[abstract]:
            return dep
        
        if marker.injects_default:
            return scope[marker.default]
        elif marker.has_default:
            return self._make_dependency(marker, scope, concrete=marker.default)







@attr.s(slots=True, cmp=False, init=False, frozen=True)
class Factory(Provider[abc.Callable[..., T_Injected], T_Injected], t.Generic[T_Injected]):
    
    arguments: tuple[tuple, frozendict] = attr.ib(default=((), frozendict()))
    # is_shared: t.ClassVar[bool] = False
    
    _signature: Signature = attr.ib(init=False, default=None)

    _blank_signature: t.ClassVar[Signature] = Signature()
    _arbitrary_signature: t.ClassVar[Signature] = Signature([
        Parameter('__Parameter_var_positional', Parameter.VAR_POSITIONAL),
        Parameter('__Parameter_var_keyword', Parameter.VAR_KEYWORD),
    ])

    _sync_dependency_class: t.ClassVar = dependency.Factory
    _async_dependency_class: t.ClassVar = dependency.AsyncFactory
    _await_params_sync_dependency_class: t.ClassVar = dependency.AwaitParamsFactory
    _await_params_async_dependency_class: t.ClassVar = dependency.AwaitParamsAsyncFactory

    def __init__(self, concrete: abc.Callable[..., T_Injectable] = None, /, *args, **kwargs) -> None:
        self.__attrs_init__(
            concrete=concrete, 
            arguments=(args, kwargs)
        )

    def args(self, *args) -> Self:
        arguments = self.arguments
        self.__setattr(arguments=(args, *arguments[1:]))
        return self

    def kwargs(self, **kwargs) -> Self:
        arguments = self.arguments
        self.__setattr(arguments=(*arguments[:1], frozendict(kwargs)))
        return self
 
    @t.overload
    def use(self) -> abc.Callable[[_T], _T]: ...

    @t.overload
    def use(self, using: abc.Callable, *args, **kwargs) -> Self: ...

    @_fluent_decorator()
    def use(self, using, *args, **kwargs):
        self.__setattr(concrete=using)
        args and self.args(*args)
        kwargs and self.kwargs(**kwargs)
        return self
        
    def signature(self, signature: Signature) -> Self:
        self.__setattr(_signature=signature)
        return self
    
    def asynchronous(self, is_async=True):
        self.__setattr(is_async=is_async)
        return self

    def get_signature(self, dep: Injectable=None):
        sig = self._signature
        if sig is None:
            try:
                return typed_signature(self.concrete)
            except ValueError:
                return self._fallback_signature()
        return sig

    def _fallback_signature(self):
        return self._arbitrary_signature if self.arguments else self._blank_signature

    def _onfreeze(self):
        if None is self.is_async:
            self.__setattr(is_async=self._is_async_factory())

    def _is_async_factory(self) -> bool:
        return iscoroutinefunction(self.concrete)

    def _bind_params(self, scope: "Scope", abstract: Injectable, *, sig=None, arguments=()):
        sig = sig or self.get_signature(abstract)
        args, kwargs = arguments or self.arguments
        return BoundParams.bind(sig, scope, self.container, args, kwargs)

    def _get_dependency_kwargs(self, **kwds):
        kwds.setdefault('concrete', self.concrete)
        return super()._get_dependency_kwargs(**kwds)

    def _make_dependency(self, abstract: T_Injectable, scope: 'Scope', **kwds):
        params = self._bind_params(scope, abstract)
        if params.is_async:
            if self.is_async:
                cls = self._await_params_async_dependency_class
            else:
                cls = self._await_params_sync_dependency_class
        elif self.is_async:
            cls = self._async_dependency_class
        else:
            cls = self._sync_dependency_class

        return cls(
            abstract, scope, self, 
            params=params, 
            **self._get_dependency_kwargs(**kwds),
        )
        



@attr.s(slots=True, cmp=False, init=False)
class Singleton(Factory[T_Injected]):

    is_shared: t.ClassVar[bool] = True
    is_thread_safe: bool = attr.ib(init=False, default=True)

    _sync_dependency_class: t.ClassVar = dependency.Singleton
    _async_dependency_class: t.ClassVar = dependency.AsyncSingleton
    _await_params_sync_dependency_class: t.ClassVar = dependency.AwaitParamsSingleton
    _await_params_async_dependency_class: t.ClassVar = dependency.AwaitParamsAsyncSingleton

    def thread_safe(self, is_thread_safe=True):
        self.__setattr(is_thread_safe=is_thread_safe)
        return self

    def _get_dependency_kwargs(self, **kwds):
        kwds.setdefault('thread_safe', self.is_thread_safe)
        return super()._get_dependency_kwargs(**kwds)






@attr.s(slots=True, cmp=False, init=False)
class Resource(Singleton[T_Injected]):

    is_async: bool = attr.ib(init=False, default=None)
    is_awaitable: bool = attr.ib(init=False, default=None)
    is_shared: t.ClassVar[bool] = True

    def awaitable(self, is_awaitable=True):
        self.__setattr(is_awaitable=is_awaitable)
        return self
        
    def _get_dependency_kwargs(self, **kwds):
        # kwds.setdefault('aw_enter', self.is_awaitable)
        return super()._get_dependency_kwargs(**kwds)




@attr.s(slots=True, init=False)
class Partial(Factory[T_Injected]):

    _sync_dependency_class: t.ClassVar = dependency.Partial
    _async_dependency_class: t.ClassVar = dependency.AsyncPartial
    _await_params_sync_dependency_class: t.ClassVar = dependency.AwaitParamsPartial
    _await_params_async_dependency_class: t.ClassVar = dependency.AwaitParamsAsyncPartial

    def _fallback_signature(self):
        return self._arbitrary_signature

    def _resolve(self, abstract: T_Injectable, scope: 'Scope') -> dependency.Dependency:
        return dependency.Dependency(scope, abstract, self)






@attr.s(slots=True, init=False)
class Callable(Partial[T_Injected]):

    _sync_dependency_class: t.ClassVar = dependency.Callable
    _async_dependency_class: t.ClassVar = dependency.AsyncCallable
    _await_params_sync_dependency_class: t.ClassVar = dependency.AwaitParamsCallable
    _await_params_async_dependency_class: t.ClassVar = dependency.AwaitParamsAsyncCallable






@attr.s(slots=True, frozen=True, cmp=False)
class ProvidedMarkerProvider(Factory):
    
    abstract = Provided
    concrete = attr.ib(init=False, default=lazy.eval)

    def _can_resolve(self, abstract: T_Injectable, scope: "Scope") -> bool:
        return isinstance(abstract, Provided)

    def _bind_params(self, scope: "Scope", marker: Provided, *, sig=None, arguments=()):
        if not arguments:
            abstract = marker.__abstract__
            arguments = (lazy.LazyOp(*marker),), frozendict(root=Dep(abstract))
        return super()._bind_params(scope, marker, sig=sig, arguments=arguments)

