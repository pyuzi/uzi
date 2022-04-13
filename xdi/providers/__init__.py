import sys
from types import GenericAlias
import typing as t
from abc import ABCMeta, abstractmethod
from collections import abc
from functools import wraps
from inspect import (Parameter, Signature, iscoroutinefunction)
from logging import getLogger

from typing_extensions import Self

import attr

from .. import (Dep, Injectable, InjectionMarker, T_Injectable, T_Injected,
                is_injectable, _dependency as dependency)
from .._common import Missing, private_setattr, typed_signature, frozendict
from .functools import BoundParams



if sys.version_info < (3, 10):  # pragma: py-gt-39
    UnionType = type(t.Union[t.Any, None])
else:                           # pragma: py-lt-310
    from types import UnionType


if t.TYPE_CHECKING:  # pragma: no cover
    from ..containers import Container
    from ..scopes import Injector, Scope




logger = getLogger(__name__)


_T = t.TypeVar("_T")
_T_Fn = t.TypeVar("_T_Fn", bound=abc.Callable, covariant=True)
_T_Concrete = t.TypeVar("_T_Concrete")

_T_Dep = t.TypeVar('_T_Dep', bound=dependency.Dependency, covariant=True)

T_Injectable = T_Injectable


_missing_or_none = frozenset([Missing, None, ...])


def _fluent_decorator(default=Missing, *, fluent: bool = False):
    def decorator(func: _T_Fn) -> _T_Fn:
        fn = func
        while hasattr(fn, "_is_fluent_decorator"):
            fn = fn.__wrapped__

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

    return decorator




class DuplicateProviderError(ValueError):
    pass





@private_setattr(frozen='_frozen')
@attr.s(slots=True, frozen=True, cmp=False)
class Provider(t.Generic[_T_Concrete, _T_Dep]):

    _frozen: bool = attr.ib(init=False, default=False)


    concrete: _T_Concrete = attr.ib()
    """The object used to resolve 
    """

    container: "Container" = attr.ib(kw_only=True, default=None) 
    """The Container where this provider is setup.
    """

    is_default: bool = attr.ib(kw_only=True, default=False)
    """Whether this provider is the default. 
    A default provider only gets used if none other was provided to override it.
    """

    # is_final: bool = attr.ib(kw_only=True, default=False)
    # """Whether this provider is final. Final providers cannot be overridden 
    # """

    filters: tuple[abc.Callable[['Scope', Injectable], bool]] = attr.ib(kw_only=False, default=(), converter=tuple)
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
   
    def when(self, *filters, append: bool=False) -> Self:
        if append:
            self.__setattr(filters=tuple(dict.fromkeys(self.filters + filters)))
        else:
            self.__setattr(filters=tuple(dict.fromkeys(filters)))
        return self

    def autoload(self, autoloaded: bool = True) -> Self:
        self.__setattr(autoloaded=autoloaded)
        return self

    def final(self, is_final: bool = True) -> Self:
        self.__setattr(is_final=is_final)
        return self

    def default(self, is_default: bool = True) -> Self:
        self.__setattr(is_default=is_default)
        return self

    @t.overload
    def using(self) -> abc.Callable[[_T], _T]:
        ...

    @t.overload
    def using(self, using: t.Any) -> Self:
        ...

    @_fluent_decorator()
    def using(self, using):
        self.__setattr(concrete=using)
        return self

    def can_compose(self, scope: "Scope", dep: T_Injectable=None) -> bool:
        self._freeze()
        if self.container is None or self.container in scope:
            return self._can_compose(scope, dep) and self._run_filters(scope, dep)
        return False

    def _can_compose(self, scope: "Scope", dep: T_Injectable) -> bool:
        return True

    def _run_filters(self, scope: "Scope", dep: T_Injectable) -> bool:
        for fl in self.filters:
            if not fl(self, scope, dep):
                return False
        return True

    def compose(self, scope: 'Scope', dep: T_Injectable):
        if self.can_compose(scope, dep):
            return self._compose(scope, dep)
    
    @abstractmethod
    def _compose(self, scope: 'Scope', dep: T_Injectable) -> dependency.Dependency:
        raise NotImplementedError(f'{self.__class__.__qualname__}._compose()')

    def _compose(self, scope: 'Scope', abstract: T_Injectable) -> dependency.Dependency:
        return self._make_dependency(abstract, scope, self)

    def _freeze(self):
        self._frozen or (self._onfreeze(), self.__setattr(_frozen=True))

    def _onfreeze(self):
        ...

    def _get_dependency_kwargs(self, **kwds):
        return self._dependency_kwargs | kwds

    def _make_dependency(self, abstract: T_Injectable, scope: 'Scope', **kwds):
        if cls := self._dependency_class:
            return cls(abstract, scope, self, **self._get_dependency_kwargs(**kwds))
        raise NotImplementedError(f'{self.__class__.__name__}.Dependency')

    def _override(self, override: Self, abstract) -> Self:
        if not self.is_final:
            return override._set_prev(self) or self
        raise DuplicateProviderError(
            f"Final provider '{self}' got '{override}' has overrides"
        )

    def _set_prev(self, prev: Self):
        return self

    def __eq__(self, x):
        return x is self

    def __hash__(self):
        return id(self)





@attr.s(slots=True, frozen=True, cmp=False)
class Value(Provider[_T_Concrete, dependency.Value]):
    """Provides given value as it is."""

    _dependency_class = dependency.Value

    def _get_dependency_kwargs(self, **kwds):
        return self._dependency_kwargs | { 'use': self.concrete } | kwds




@attr.s(slots=True, frozen=True, cmp=False)
class Alias(Provider[_T_Concrete]):

    def _compose(self, scope: 'Scope', dep: T_Injectable):
        return scope[self.concrete]
  
  

@attr.s(slots=True, frozen=True, cmp=False)
class UnionProvider(Provider[_T_Concrete]):

    concrete = attr.ib(default=UnionType)


    def get_all_args(self, token: Injectable):
        return t.get_args(token)

    def _compose(self, scope: 'Scope', dep: T_Injectable):
        container = self.container
        for arg in self.get_all_args(dep):
            if is_injectable(arg):
                if rv := scope[arg]:
                    return rv



@attr.s(slots=True, frozen=True, cmp=False)
class AnnotatedProvider(UnionProvider[_T_Concrete]):

    concrete = attr.ib(default=type(t.Annotated[t.Any, 'ann']))

    def get_all_args(self, token: t.Annotated):
        return token.__metadata__[::-1] + (token.__args__,)
  
  



@attr.s(slots=True, frozen=True, cmp=False)
class DepMarkerProvider(Provider):
    
    concrete = attr.ib(default=Dep)

    def _provides_fallback(self):
        return self.concrete

    def _can_compose(self, scope: "Scope", obj: Dep) -> bool:
        return isinstance(obj, self.concrete) and ( 
                obj.__injector__ is None
                or obj.__injector__ in Dep.Flag
                or obj.__injector__ in scope
            )
    
    def _compose(self, scope: 'Scope', marker: Dep) -> dependency.Dependency:
        dep = marker.__injects__
        flag = marker.__injector__
        default = marker.__default__

        return super()._compose(scope, dep)

    def _bind(self, scope: "Scope", marker: Dep):
        dep = marker.__injects__
        flag = marker.__injector__
        default = marker.__default__
        if not (inject_default := isinstance(default, InjectionMarker)):
            default = marker.__hasdefault__ and (lambda: default) or None
            if default:
                default.is_async = False

        if flag is Dep.ONLY_SELF:
            def run(ctx: 'Injector'):
                func = ctx.get(dep)
                if None is func:
                    return ctx[default] if inject_default is True else default
                elif True is getattr(func, 'is_async', False):
                    async def make():
                        nonlocal func, marker
                        return marker.__eval__(await func())
                    make.is_async = True
                    return make
                else:
                    async def make():
                        nonlocal func, marker
                        return marker.__eval__(func())

                    make.is_async = False
                    return make

        elif flag is Dep.SKIP_SELF:
            def run(ctx: 'Injector'):
                func = ctx.parent[dep] 
                if None is func:
                    return ctx[default] if inject_default is True else default
                elif True is getattr(func, 'is_async', False):
                    async def make():
                        nonlocal func, marker
                        return marker.__eval__(await func())
                    make.is_async = True
                    return make
                else:
                    async def make():
                        nonlocal func, marker
                        return marker.__eval__(func())

                    make.is_async = False
                    return make
        else:
            def run(ctx: 'Injector'):
                func = ctx[dep] 
                if None is func:
                    return ctx[default] if inject_default is True else default
                elif True is getattr(func, 'is_async', False):
                    async def make():
                        nonlocal func, marker
                        return marker.__eval__(await func())
                    make.is_async = True
                    return make
                else:
                    async def make():
                        nonlocal func, marker
                        return marker.__eval__(func())

                    make.is_async = False
                    return make
                

        return run, {dep}




_none_or_ellipsis = frozenset([None, ...])



@attr.s(slots=True, init=False, frozen=True)
class Factory(Provider[abc.Callable[..., T_Injected], T_Injected], t.Generic[T_Injected]):
    
    arguments: tuple[tuple, frozendict] = attr.ib(default=((), frozendict()))
    # is_shared: t.ClassVar[bool] = False
    
    _signature: Signature = attr.ib(init=False, default=None)

    _blank_signature: t.ClassVar[Signature] = Signature()
    _arbitrary_signature: t.ClassVar[Signature] = Signature([
        Parameter('__Parameter_var_positional', Parameter.VAR_POSITIONAL),
        Parameter('__Parameter_var_keyword', Parameter.VAR_KEYWORD),
    ])

    # decorators: tuple[abc.Callable[[abc.Callable], abc.Callable]] = ()
    # _all_decorators: tuple[abc.Callable[[abc.Callable], abc.Callable]]

    # _binding_class: t.ClassVar[type[FactoryBinding]] = FactoryBinding
    _dependency_class: t.ClassVar = dependency.Factory

    def __init__(self, concrete: abc.Callable[..., T_Injectable] = None, /, *args, **kwargs) -> None:
        self.__attrs_init__(
            concrete=concrete, 
            arguments=(args, kwargs)
        )

    # @Provider.concrete.setter
    # def concrete(self, value):
    #     if not isinstance(value, AbstractCallable):
    #         raise ValueError(f'must be a `Callable` not `{value}`')
    #     self.__setattr(concrete=value)
    #     self._is_registered or self._register()
    
    def args(self, *args) -> Self:
        arguments = self.arguments
        self.__setattr(arguments=(args, *arguments[1:]))
        return self

    def kwargs(self, **kwargs) -> Self:
        arguments = self.arguments
        self.__setattr(arguments=(*arguments[:1], frozendict(kwargs)))
        return self
        
    def singleton(self, is_singleton: bool = True, *, thread_safe: bool=False) -> Self:
        self.__setattr(is_shared=is_singleton, thread_safe=thread_safe)
        return self

    @t.overload
    def using(self) -> abc.Callable[[_T], _T]:
        ...

    @t.overload
    def using(self, using: abc.Callable, *args, **kwargs) -> Self:
        ...

    @_fluent_decorator()
    def using(self, using, *args, **kwargs):
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

    # def _provides_fallback(self):
    #     return self.concrete

    # def _bind(self, scope: "Scope", token: T_Injectable) :
    #     return self._create_binding(scope), None

    # def _create_binding(self, scope: "Scope"):
    #     return self._binding_class(
    #             scope,
    #             self.concrete, 
    #             self.container,
    #             self.get_signature(),
    #             is_async=self.is_async,
    #             arguments=self.arguments, 
    #         )

    def _bind_params(self, scope: "Scope", dep: Injectable):
        sig = self.get_signature(dep)
        args, kwargs = self.arguments
        return BoundParams.bind(sig, scope, self.container, args, kwargs)

    def _compose(self, scope: 'Scope', dep: T_Injectable):
        params = self._bind_params(scope, dep)
        return self._dependency_class(
            dep, scope, self, 
            use=self.concrete, 
            params=params, 
            async_call=self.is_async
        )





@attr.s(slots=True, init=False)
class Singleton(Factory[T_Injected]):

    is_shared: t.ClassVar[bool] = True
    is_thread_safe: bool = attr.ib(init=False, default=True)
    # _binding_class: t.ClassVar[type[SingletonFactoryBinding]] = SingletonFactoryBinding
    _dependency_class: t.ClassVar = dependency.Singleton

    def thread_safe(self, is_thread_safe=True):
        self.__setattr(is_thread_safe=is_thread_safe)
        return self

    # def _create_binding(self, scope: "Scope"):
    #     return self._binding_class(
    #             scope,
    #             self.concrete, 
    #             self.container,
    #             self.get_signature(),
    #             is_async=self.is_async,
    #             arguments=self.arguments, 
    #             thread_safe=self.is_thread_safe
    #         )

    def _compose(self, scope: 'Scope', dep: T_Injectable):
        params = self._bind_params(scope, dep)
        return self._dependency_class(
            dep, scope, self, 
            use=self.concrete, 
            params=params, 
            async_call=self.is_async,
            thread_safe=self.is_thread_safe
        )





@attr.s(slots=True, init=False)
class Resource(Singleton[T_Injected]):

    is_async: bool = attr.ib(init=False, default=None)
    is_awaitable: bool = attr.ib(init=False, default=None)
    is_shared: t.ClassVar[bool] = True

    # _binding_class: t.ClassVar[type[ResourceFactoryBinding]] = ResourceFactoryBinding
    _dependency_class: t.ClassVar = dependency.Resource

    def awaitable(self, is_awaitable=True):
        self.__setattr(is_awaitable=is_awaitable)
        return self
        
    # def _create_binding(self, scope: "Scope"):
    #     return self._binding_class(
    #             scope,
    #             self.concrete, 
    #             self.container,
    #             self.get_signature(),
    #             is_async=self.is_async,
    #             aw_enter=self.is_awaitable,
    #             arguments=self.arguments, 
    #         )

    def _compose(self, scope: 'Scope', dep: T_Injectable):
        params = self._bind_params(scope, dep)
        return self._dependency_class(
            dep, scope, self, 
            use=self.concrete, 
            params=params, 
            async_call=self.is_async,
            thread_safe=self.is_thread_safe,
            aw_enter=self.is_awaitable
        )



@attr.s(slots=True, init=False)
class Partial(Factory[T_Injected]):

    # _binding_class: t.ClassVar[type[PartialFactoryBinding]] = PartialFactoryBinding

    def _fallback_signature(self):
        return self._arbitrary_signature

    def _create_binding(self, scope: "Scope"):
        return self._binding_class(
                scope,
                self.concrete, 
                self.container,
                self.get_signature(),
                is_async=self.is_async,
                arguments=self.arguments, 
            )

    def _compose(self, scope: 'Scope', dep: T_Injectable) -> dependency.Dependency:
        return dependency.Dependency(scope, dep, self)






@attr.s(slots=True, init=False)
class Callable(Partial[T_Injected]):
    ...

    # _binding_class: t.ClassVar[type[CallableFactoryBinding]] = CallableFactoryBinding



