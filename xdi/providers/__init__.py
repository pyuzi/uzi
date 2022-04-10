import sys
from types import GenericAlias
import typing as t
from abc import ABCMeta, abstractmethod
from collections import abc
from collections.abc import Callable as AbstractCallable
from collections.abc import Iterable, Set
from functools import wraps
from inspect import (Parameter, Signature, iscoroutinefunction)
from logging import getLogger

from typing_extensions import Self

import attr

from .. import (Dep, Injectable, InjectionMarker, T_Injectable, T_Injected,
                is_injectable, _dependency as dependency)
from .._common import Missing, typed_signature
from .._dependency import Dependency
from .._common.collections import Arguments
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
_T_Using = t.TypeVar("_T_Using")


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



class ProviderType(type):

    def __new__(mcls, name: str, bases: tuple[type], ns: dict, **kwds):
        attrset = f"_{name}__set_attr"
        if attrset not in ns:
            ns[attrset] = getattr(Provider, "_Provider__set_attr")

        cls = super().__new__(mcls, name, bases, ns)
        return cls




@InjectionMarker.register
@attr.s(slots=True, frozen=True, init=False)
class Provider(t.Generic[_T_Using, T_Injected]): #, metaclass=ProviderType):

    _frozen: bool = attr.field(init=False, default=False)

    _is_registered: bool = attr.field(init=False, default=False)

    container: "Container" = attr.field(init=False, default=None)
    """The Container where this provider is setup.
    """

    autoloaded: bool = attr.field(init=False, default=False)

    is_default: bool = attr.field(init=False, default=False)
    """Whether this provider is the default. 
    A default provider only gets used if none other was provided to override it.
    """

    is_final: bool = attr.field(init=False, default=False)
    """Whether this provider is final. Final providers cannot be overridden 
    """

    _provides: T_Injectable = attr.field(init=False, default=Missing)
    """The Injectable/token provided by this provider
    """

    _uses: _T_Using = attr.field(init=False, default=Missing)
    """The object used to resolve 
    """

    is_shared: t.ClassVar[bool] = attr.field(init=False, default=None)
    """Whether this provided value is shared.
    """

    is_async: bool = attr.field(init=False, default=None)
    """Whether the value is provided async.
    """

    filters: tuple[abc.Callable[['Scope', Injectable], bool]] = attr.field(init=False, default=())
    """Called to determine whether this provider can be bound.
    """
    __class_getitem__ = classmethod(GenericAlias)

    def __init_subclass__(cls, *args, **kwargs):
        if not hasattr(cls, fn := f'_{cls.__name__}__set_attr'):
            setattr(cls, fn, getattr(Provider, '_Provider__set_attr'))

    def __init__(self, provide: Injectable = Missing, using: Injectable = Missing) -> None:
        # self.__init_attrs__()
        self.__attrs_init__()
        using in _missing_or_none or self.using(using)
        provide in _missing_or_none or self.provide(provide)

    @property
    def __dependency__(self):
        if self.container is None:
            return self
        raise ValueError(f'provider is registered to {self.container}')

    @property
    def provides(self) -> T_Injectable:
        """The Injectable/token provided by this provider"""
        val = self._provides
        if val is Missing:
            val = self._provides_fallback()
            if val is Missing:
                raise AttributeError(f'{"provides"!r} in {self}')
        return val

    @provides.setter
    def provides(self, val):
        if self._is_registered:
            raise AttributeError(f"{self} already registered.")
        elif not is_injectable(val):
            raise ValueError(f'{self.__class__.__name__}.provides must be an `Injectable` not `{val!r}`')
        else:
            self.__set_attr(_provides=val)
            self._register()

    @property
    def uses(self) -> _T_Using:
        val = self._uses
        if val is Missing:
            val = self._uses_fallback()
            if val is Missing:
                raise AttributeError(f'{"uses"!r} in {self}')
        return val

    @uses.setter
    def uses(self, val):
        self.__set_attr(_uses=val)
        self._is_registered or self._register()

    def _uses_fallback(self):
        return Missing

    def _provides_fallback(self):
        return Missing

    def set_container(self, container: "Container") -> Self:
        if not self.container is None:
            if not container is self.container:
                raise AttributeError(
                    f"container for `{self}` already set to `{self.container}`."
                )
        else:
            self.__set_attr(container=container)
            self._register()
        return self
   
    def _register(self):
        if self._is_registered is False:
            if self._prepare_to_register():
                self.__set_attr(_is_registered=True)
                self.container.add_to_registry(self.provides, self)
        else:
            raise TypeError(f'{self!s} already registered to {self.container}.')

    def _prepare_to_register(self):
        if not self._frozen:
            if self._is_registered:
                raise TypeError(f'{self!s} already registered to {self.container}.')
            try:
                uses = self.uses
                provides = self.provides
            except AttributeError:
                return False
            else:
                uses == self._uses or self.__set_attr(_uses=uses)    
                provides == self._provides or self.__set_attr(_provides=provides)
                return not self.container is None
        return False
      
    def when(self, *filters, append: bool=False) -> Self:
        if append:
            self.__set_attr(filters=tuple(dict.fromkeys(self.filters + filters)))
        else:
            self.__set_attr(filters=tuple(dict.fromkeys(filters)))
        return self

    def autoload(self, autoloaded: bool = True) -> Self:
        self.__set_attr(autoloaded=autoloaded)
        return self

    def final(self, is_final: bool = True) -> Self:
        self.__set_attr(is_final=is_final)
        return self

    def default(self, is_default: bool = True) -> Self:
        self.__set_attr(is_default=is_default)
        return self

    @t.overload
    def provide(self) -> abc.Callable[[T_Injectable], T_Injectable]:
        ...

    @t.overload
    def provide(self, provide: T_Injectable) -> Self:
        ...

    @_fluent_decorator()
    def provide(self, provide: T_Injectable):
        self.__set_attr(provides=provide)
        return self

    @t.overload
    def using(self) -> abc.Callable[[_T], _T]:
        ...

    @t.overload
    def using(self, using: t.Any) -> Self:
        ...

    @_fluent_decorator()
    def using(self, using):
        self.__set_attr(uses=using)
        return self

    def bind(self, scope: "Scope", provides: T_Injectable=None) :
        self._freeze()

        if self.container is None or self.container in scope:
            fn, deps = self._bind(scope, provides)
            return fn

    @abstractmethod
    def _bind(self, scope: "Scope", token: T_Injectable) -> tuple[abc.Callable, Set]:
        ...

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

    def compose(self, scope: 'Scope', dep: T_Injectable, *overrides: Self):
        if overrides and (child := overrides[0].compose(scope, dep, *overrides[1:])): 
            if not self.is_final:
                return child
            raise DuplicateProviderError(
                f"Final provider '{self}' got '{1+len(overrides)}' has overrides"
            )
        elif self.can_compose(scope, dep):
            return self._compose(scope, dep)
    
    @abstractmethod
    def _compose(self, scope: 'Scope', dep: T_Injectable) -> dependency.Dependency:
        raise NotImplementedError(f'{self.__class__.__qualname__}._compose()')

    def _compose(self, scope: 'Scope', dep: T_Injectable) -> dependency.Dependency:
        return dependency.Dependency(scope, dep, self)

    def _freeze(self):
        self._frozen or (self._onfreeze(), self.__set_attr(_frozen=True))

    def _onfreeze(self):
        ...

    # def __str__(self):
    #     using = self._uses_fallback() if self._uses is Missing else self._uses
    #     return f"{self.__class__.__name__}({using})"

    # def __repr__(self):
    #     using = self._uses_fallback() if self._uses is Missing else self._uses
    #     provides = (
    #         self._provides_fallback() if self._provides is Missing else self._provides
    #     )
    #     container = self.container
    #     return f"{self.__class__.__name__}({provides=!r}, {using=!r}, {container=!r})"

    @t.final
    def __set_attr(self, name=None, value=None, force=False, /, **kw):
        name is None or (kw := {name: value})

        if force is False and self._frozen:
            raise AttributeError(f"`cannot set {tuple(kw)} on frozen {self}.")
        
        for k,v in kw.items():
            object.__setattr__(self, k, v)

   
   


class Value(Provider[T_Injected, T_Injected]):
    """Provides given value as it is."""

    is_shared: t.ClassVar[bool] = True

    # if t.TYPE_CHECKING:
    #     def __init__(self, provide: Injectable = Missing, value: T_Injected = Missing) -> None:
    #         ...

    def _compose(self, scope: 'Scope', dep: T_Injectable):
        return dependency.Value(scope, dep, self, use=self.uses)

    # def _bind(self, scope: "Scope", dep: T_Injectable) :
    #     value = self.uses
    #     def make():
    #         nonlocal value
    #         return value
        
    #     return lambda ctx: make, None
    
    # def _compose(self, scope: 'Scope', dep: T_Injectable, overrides: tuple[Self]=()) -> dependency.Dependency:
    #     raise NotImplementedError(f'{self.__class__.__qualname__}._compose()')






class Alias(Provider[T_Injectable, T_Injected]):


    # if t.TYPE_CHECKING:
    #     def __init__(self, provide: Injectable = Missing, alias: Injectable = Missing) -> None:
    #         ...
    
    def _compose(self, scope: 'Scope', dep: T_Injectable):
        return scope[self.uses:self.container]
        # if use := scope[self.uses:self.container]:
            # return dependency.Alias(scope, dep, self, use=use)

    # def _can_compose(self, scope: "Scope", obj: T_Injectable) -> bool:
    #     return obj != self.uses and scope.is_provided(self.uses)

    # def _bind(self, scope: "Scope", obj: T_Injectable) :
    #     real = self.uses
    #     return lambda ctx: ctx[real], {real}




class UnionProvider(Provider[_T_Using, T_Injected]):

    _bind_type = UnionType 
    _uses = UnionType

    def _provides_fallback(self):
        return UnionType

    def get_all_args(self, token: Injectable):
        return t.get_args(token)

    # def _iter_injectables(self, scope: 'Scope', token: Injectable) -> tuple[Injectable]:
    #     for a in self.get_all_args(token):
    #         if is_injectable(a):
    #             yield a
                
    # def _is_bind_type(self, obj: T_Injectable):
    #     return isinstance(obj, self._bind_type)

    # def _can_compose(self, scope: "Scope", obj: T_Injectable) -> bool:
    #     return self._is_bind_type(obj) and next(self._iter_injectable(scope, obj), ...)

    # def _bind(self, scope: "Scope", obj):
    #     if deps := [*self._iter_injectables(scope, obj)]:
    #         return lambda ctx: ctx.find(*deps), {*deps}
    #     return None, None

    def _compose(self, scope: 'Scope', dep: T_Injectable):
        container = self.container
        for arg in self.get_all_args(dep):
            if is_injectable(arg):
                if rv := scope[arg:container]:
                    return rv

    # def _compose(self, scope: 'Scope', dep: T_Injectable):
    #     return dependency.Union(scope, dep, self, use=self.uses)




class AnnotatedProvider(UnionProvider):

    _uses: t.Final = type(t.Annotated)
    # _bind_type = type(t.Annotated[t.Any, 'ann']) 

    def get_all_args(self, token: t.Annotated):
        return token.__metadata__[::-1] + (token.__args__,)
  
    def _provides_fallback(self):
        return t.Annotated





class DepMarkerProvider(Provider):
    
    _uses: t.ClassVar = Dep

    def _provides_fallback(self):
        return self.uses

    def _can_compose(self, scope: "Scope", obj: Dep) -> bool:
        return isinstance(obj, self.uses) and ( 
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
    
    arguments: Arguments = attr.field(init=False, factory=Arguments)
    is_shared: t.ClassVar[bool] = False
    
    _signature: Signature = attr.field(init=False, default=None)

    _blank_signature: t.ClassVar[Signature] = Signature()
    _arbitrary_signature: t.ClassVar[Signature] = Signature([
        Parameter('__Parameter_var_positional', Parameter.VAR_POSITIONAL),
        Parameter('__Parameter_var_keyword', Parameter.VAR_KEYWORD),
    ])

    # decorators: tuple[abc.Callable[[abc.Callable], abc.Callable]] = ()
    # _all_decorators: tuple[abc.Callable[[abc.Callable], abc.Callable]]

    # _binding_class: t.ClassVar[type[FactoryBinding]] = FactoryBinding
    _dependency_class: t.ClassVar = dependency.Factory

    def __init__(self, provide: abc.Callable[..., T_Injectable] = None, /, *args, **kwargs) -> None:
        self.__attrs_init__()
        if not provide in _none_or_ellipsis:
            self.provide(provide)
            callable(provide) and self.using(provide)
        args and self.args(*args)
        kwargs and self.kwargs(**kwargs)

    @Provider.uses.setter
    def uses(self, value):
        if not isinstance(value, AbstractCallable):
            raise ValueError(f'must be a `Callable` not `{value}`')
        self.__set_attr(_uses=value)
        self._is_registered or self._register()
    
    def args(self, *args) -> Self:
        arguments = self.arguments
        self.__set_attr(arguments=Arguments(args, arguments.kwargs))
        return self

    def kwargs(self, **kwargs) -> Self:
        arguments = self.arguments
        self.__set_attr(arguments=Arguments(arguments.args, kwargs))
        return self
        
    def singleton(self, is_singleton: bool = True, *, thread_safe: bool=False) -> Self:
        self.__set_attr(is_shared=is_singleton, thread_safe=thread_safe)
        return self

    @t.overload
    def using(self) -> abc.Callable[[_T], _T]:
        ...

    @t.overload
    def using(self, using: abc.Callable, *args, **kwargs) -> Self:
        ...

    @_fluent_decorator()
    def using(self, using, *args, **kwargs):
        self.__set_attr(uses=using)
        args and self.args(*args)
        kwargs and self.kwargs(**kwargs)
        return self
        
    def signature(self, signature: Signature) -> Self:
        self.__set_attr(_signature=signature)
        return self
    
    def asynchronous(self, is_async=True):
        self.__set_attr(is_async=is_async)
        return self

    def get_signature(self, dep: Injectable=None):
        sig = self._signature
        if sig is None:
            try:
                return typed_signature(self.uses)
            except ValueError:
                return self._fallback_signature()
        return sig

    def _fallback_signature(self):
        return self._arbitrary_signature if self.arguments else self._blank_signature

    def _onfreeze(self):
        if None is self.is_async:
            self.__set_attr(is_async=self._is_async_factory())

    def _is_async_factory(self) -> bool:
        return iscoroutinefunction(self.uses)

    def _provides_fallback(self):
        return self._uses

    def _bind(self, scope: "Scope", token: T_Injectable) :
        return self._create_binding(scope), None

    # def _create_binding(self, scope: "Scope"):
    #     return self._binding_class(
    #             scope,
    #             self.uses, 
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
            scope, dep, self, 
            use=self.uses, 
            params=params, 
            async_call=self.is_async
        )





@attr.s(slots=True, init=False)
class Singleton(Factory[T_Injected]):

    is_shared: t.ClassVar[bool] = True
    is_thread_safe: bool = attr.field(init=False, default=True)
    # _binding_class: t.ClassVar[type[SingletonFactoryBinding]] = SingletonFactoryBinding
    _dependency_class: t.ClassVar = dependency.Singleton

    def thread_safe(self, is_thread_safe=True):
        self.__set_attr(is_thread_safe=is_thread_safe)
        return self

    # def _create_binding(self, scope: "Scope"):
    #     return self._binding_class(
    #             scope,
    #             self.uses, 
    #             self.container,
    #             self.get_signature(),
    #             is_async=self.is_async,
    #             arguments=self.arguments, 
    #             thread_safe=self.is_thread_safe
    #         )

    def _compose(self, scope: 'Scope', dep: T_Injectable):
        params = self._bind_params(scope, dep)
        return self._dependency_class(
            scope, dep, self, 
            use=self.uses, 
            params=params, 
            async_call=self.is_async,
            thread_safe=self.is_thread_safe
        )





@attr.s(slots=True, init=False)
class Resource(Singleton[T_Injected]):

    is_async: bool = attr.field(init=False, default=None)
    is_awaitable: bool = attr.field(init=False, default=None)
    is_shared: t.ClassVar[bool] = True

    # _binding_class: t.ClassVar[type[ResourceFactoryBinding]] = ResourceFactoryBinding
    _dependency_class: t.ClassVar = dependency.Resource

    def awaitable(self, is_awaitable=True):
        self.__set_attr(is_awaitable=is_awaitable)
        return self
        
    # def _create_binding(self, scope: "Scope"):
    #     return self._binding_class(
    #             scope,
    #             self.uses, 
    #             self.container,
    #             self.get_signature(),
    #             is_async=self.is_async,
    #             aw_enter=self.is_awaitable,
    #             arguments=self.arguments, 
    #         )

    def _compose(self, scope: 'Scope', dep: T_Injectable):
        params = self._bind_params(scope, dep)
        return self._dependency_class(
            scope, dep, self, 
            use=self.uses, 
            params=params, 
            async_call=self.is_async,
            thread_safe=self.is_thread_safe,
            aw_enter=self.is_awaitable
        )



class Partial(Factory[T_Injected]):

    # _binding_class: t.ClassVar[type[PartialFactoryBinding]] = PartialFactoryBinding

    def _fallback_signature(self):
        return self._arbitrary_signature

    def _create_binding(self, scope: "Scope"):
        return self._binding_class(
                scope,
                self.uses, 
                self.container,
                self.get_signature(),
                is_async=self.is_async,
                arguments=self.arguments, 
            )

    def _compose(self, scope: 'Scope', dep: T_Injectable) -> dependency.Dependency:
        return dependency.Dependency(scope, dep, self)






class Callable(Partial[T_Injected]):
    ...

    # _binding_class: t.ClassVar[type[CallableFactoryBinding]] = CallableFactoryBinding



