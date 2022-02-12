# from __future__ import annotations
from email.policy import default
from functools import lru_cache, wraps
from inspect import ismemberdescriptor, signature
from logging import getLogger
from operator import is_
from types import FunctionType, GenericAlias, new_class
import typing as t
from inspect import Parameter, Signature
from abc import ABC, ABCMeta, abstractmethod
from laza.common.collections import Arguments, frozendict, orderedset

from collections import ChainMap
from collections.abc import Callable, Set, Mapping
from laza.common.typing import get_args, typed_signature, Self, get_origin


from laza.common.functools import Missing, export, cache


from laza.common.enum import BitSetFlag, auto
from laza.common.collections import fallbackdict


from .vars import ScopeVar, FactoryScopeVar, SingletonScopeVar, ValueScopeVar, Scope
from .common import (
    Dep,
    InjectedLookup,
    Injectable,
    Depends,
    T_Injected,
    T_Injectable,
)
from .functools import FactoryResolver, PartialFactoryResolver, singleton_decorator


if t.TYPE_CHECKING:
    from .containers import IocContainer
    from .injectors import Injector


logger = getLogger(__name__)


_T = t.TypeVar("_T")
_T_Fn = t.TypeVar("_T_Fn", bound=Callable, covariant=True)
_T_Using = t.TypeVar("_T_Using")

_EMPTY = Parameter.empty

T_UsingAlias = T_Injectable
T_UsingVariant = T_Injectable
T_UsingValue = T_Injected

T_UsingFunc = Callable[..., T_Injected]
T_UsingType = type[T_Injected]

T_UsingCallable = t.Union[T_UsingType, T_UsingFunc]


T_UsingAny = t.Union[T_UsingCallable, T_UsingAlias, T_UsingValue]


def _fluent_decorator(default=Missing, *, fluent: bool = False):
    def decorator(func: _T_Fn) -> _T_Fn:

        if t.TYPE_CHECKING:

            @t.overload
            def wrapper(self, v, *a, **kwds) -> Self:
                ...

            @t.overload
            def wrapper(self, **kwds) -> Callable[[_T], _T]:
                ...

            if fluent is True:

                @wraps(func)
                def wrapper(
                    self, v=default, /, *args, **kwds
                ) -> t.Union[_T, Callable[..., _T]]:
                    ...

            else:

                @wraps(func)
                def wrapper(
                    self, v: _T = default, /, *args, **kwds
                ) -> t.Union[_T, Callable[..., _T]]:
                    ...

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


class Flag(BitSetFlag):
    aot: "Flag" = auto()
    """Compile the provider `Ahead of Time`
    """
    shared: "Flag" = auto()
    """Compile the provider `Ahead of Time`
    """


class ProviderCondition(Callable[..., bool]):

    __class_getitem__ = classmethod(GenericAlias)

    def __call__(
        self, provider: "Provider", scope: "Injector", key: T_Injectable
    ) -> bool:
        ...


@export()
class Handler(t.Protocol[T_Injected]):

    deps: t.Optional[Set[T_Injectable]]

    def __call__(self, scope: "Scope", token: T_Injectable = None) -> ScopeVar:
        ...


class _Attr(t.Generic[_T]):

    __slots__ = (
        "default",
        "__call__",
    )

    def __new__(
        cls: type[Self], default: _T = ..., *, default_factory: Callable[[], _T] = ...
    ) -> Self:
        if isinstance(default, cls):
            return default

        self = object.__new__(cls)
        if default_factory is ... is default:
            raise ValueError(f"default not provided")
        elif default_factory is ...:

            def __call__():
                return default

        else:
            __call__ = default_factory

        self.default = default
        self.__call__ = __call__
        return self

    def __set_name__(self, owner, name):
        raise RuntimeError(f"{self.__class__.__name__} is not a true destcriptor.")


class ProviderType(ABCMeta):

    _tp__uses: t.Final[type[_T_Using]] = None
    _tp__provides: t.Final[type[T_Injected]] = None

    def __new__(mcls, name: str, bases: tuple[type], ns: dict, **kwds):
        ann = ns.setdefault("__annotations__", {})

        if "__setattr__" not in ns:
            ns["__setattr__"] = Provider.__frozen_setattr__

        attrset = f"_{name}__set_attr"
        if attrset not in ns:
            ns[attrset] = Provider.__setattr__

        slots = tuple(
            n
            for n, a in ann.items()
            if (get_origin(a) or a) not in (t.ClassVar, n in ns or t.Final)
        )

        ns.setdefault("__slots__", slots)
        ns["__attr_defaults__"] = None

        defaults = ChainMap(
            {n: ns.pop(n) for n in slots if n in ns},
            *(b.__attr_defaults__ for b in bases if isinstance(b, ProviderType)),
        )

        cls = super().__new__(mcls, name, bases, ns)

        cls.__attr_defaults__ = {
            n: _Attr(v)
            for n, v in defaults.items()
            if not hasattr(cls, n) or ismemberdescriptor(getattr(cls, n))
        }

        return cls


@export()
class Provider(t.Generic[_T_Using, T_Injected], metaclass=ProviderType):

    __attr_defaults__: t.Final[dict[str, _Attr]] = ...

    static: t.ClassVar[bool] = False

    container: "IocContainer"
    """The IocContainer where this provider is setup.
    """



    is_default: bool = False
    """Whether this provider is the default. 
    A default provider only gets used if none other was provided to override it.
    """

    is_final: bool = False
    """Whether this provider is final. Final providers cannot be overridden 
    """

    is_setup: bool = False
    """Whether or not this provider is setup.
    """

    _provides: T_Injectable = Missing
    """The Injectable/token provided by this provider
    """

    _uses: _T_Using = Missing
    """The object used to resolve 
    """

    def __init__(self, provide: Injectable = Missing, using=Missing) -> None:
        self.__init_attrs__()
        provide is Missing or self.provide(provide)
        using is Missing or self.using(using)

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
        if self._provides is Missing:
            self.__set_attr("_provides", val)
        elif val is not self._provides:
            raise AttributeError(
                f"cannot {val=}. {self} already provides {self._provides}."
            )
        self.is_setup or self._setup()

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
        self.__set_attr("_uses", val)
        self.is_setup or self._setup()

    def _uses_fallback(self):
        return Missing

    def _provides_fallback(self):
        return Missing

    def setup(self, container: "IocContainer") -> Self:
        if hasattr(self, "container"):
            if self.container is not container:
                raise RuntimeError(
                    f"container for `{self}` already set to `{self.container}`."
                )
            elif self.is_setup is True:
                return self
        else:
            self.__set_attr("container", container)

        self._setup()
        return self

    def _setup(self):
        if self.is_setup:
            raise RuntimeError(
                f"provider `{self}` already setup in `{self.container}`."
            )
        elif self._can_setup():
            print(f"   - {self}.setup()")
            self.__set_attr("is_setup", True)
            self._add_to_container()

    def _add_to_container(self):
        self.container.register_provider(self)

    def _can_setup(self):
        if self.is_setup:
            return False
        try:
            self.provides, self.container, self.uses
            return True
        except AttributeError:
            return False

    def final(self, is_final: bool = True) -> Self:
        self.__set_attr("is_final", is_final)
        return self

    def default(self, is_default: bool = True) -> Self:
        self.__set_attr("is_default", is_default)
        return self

    @t.overload
    def provide(self) -> Callable[[T_Injectable], T_Injectable]:
        ...

    @t.overload
    def provide(self, provide: T_Injectable) -> Self:
        ...

    @_fluent_decorator()
    def provide(self, provide: T_Injectable):
        self.__set_attr("provides", provide)
        return self

    @t.overload
    def using(self) -> Callable[[_T], _T]:
        ...

    @t.overload
    def using(self, using: t.Any) -> Self:
        ...

    @_fluent_decorator()
    def using(self, using):
        self.__set_attr("uses", using)
        return self

    def bind(self, injector: "Injector", token: T_Injectable) -> Handler:
        fn, deps = self._bind(injector, token)
        return fn

    @abstractmethod
    def _bind(self, injector: "Injector", token: T_Injectable) -> tuple[Callable, Set]:
        ...

    def __init_attrs__(self):
        for k, attr in self.__attr_defaults__.items():
            self.__set_attr(k, attr(), force=True)

    def __str__(self):
        provides = (
            self._provides_fallback() if self._provides is Missing else self._provides
        )
        return f"{self.__class__.__name__}({provides})"

    def __repr__(self):
        using = self._uses_fallback() if self._uses is Missing else self._uses
        provides = (
            self._provides_fallback() if self._provides is Missing else self._provides
        )
        container = getattr(self, "container", None)
        return f"{self.__class__.__name__}({provides=!r}, {using=!r}, {container=!r})"

    # @t.Final
    def __setattr__(self, name, value, *, force=False):
        if not force and self.is_setup:
            raise AttributeError(f"{self.__class__.__name__}.{name} is not writable")
        object.__setattr__(self, name, value)

    if t.TYPE_CHECKING:
        t.Final

        def __set_attr(self, name, value) -> Self:
            ...

    __set_attr = __setattr__

    # @t.Final
    def __frozen_setattr__(self, name, value):
        getattr(self, name)
        AttributeError(f"{self.__class__.__name__}.{name} is not writable")


@export()
class Value(Provider[T_UsingValue, T_Injected]):
    """Provides given value as it is."""

    def _bind(self, injector: "Injector", dep: T_Injectable) -> Handler:
        value = self.uses
        func = lambda at, key: lambda: value
        return func, None


@export()
class Alias(Provider[T_UsingAlias, T_Injected]):

    def _bind(self, injector: "Injector", dep: T_Injectable) -> Handler:
        real = self.uses

        def resolver(at: "Scope", dep: T_Injectable):
            nonlocal real
            return at[real]

        return resolver, {real}



@export()
class UnionProvider(Alias):

    provides = t.Union
    uses = t.Union

    _implicit_types_ = frozenset([type(None)])

    def get_all_args(self, token: Injectable):
        return get_args(token)

    def get_injectable_args(
        self, token: Injectable, *, include_implicit=True
    ) -> tuple[Injectable]:
        implicits = self._implicit_types_ if include_implicit else set()
        return tuple(
            a
            for a in self.get_all_args(token)
            if a in implicits or self.container.is_provided(a)
        )

    # def can_provide(self, scope: 'Injector', token: Injectable) -> bool:
    #     return len(self.get_injectable_args(scope, token, include_implicit=False)) > 0

    def _bind(self, injector: "Injector", token):

        args = self.get_injectable_args(token)

        def resolver(scp: "Scope", token):
            nonlocal args
            for a in args:
                v = scp.get(a)
                if not v is None:
                    return v

        return resolver, {*args}


@export()
class AnnotatedProvider(UnionProvider):

    # use: InitVar[_T_Using] = t.Annotated
    uses: t.Final = t.Annotated

    _implicit_types_ = frozenset()

    def get_all_args(self, token: Injectable):
        return token.__metadata__[::-1]


@export()
class DependencyProvider(Alias):
    def _bind(self, injector: "Injector", token: "Depends") -> Handler:

        dep = token.on
        arguments = token.arguments or None

        if arguments:
            args, kwargs = arguments.args, arguments.kwargs
            def resolver(scp: "Scope", token):
                nonlocal dep
                inner = scp[dep]
                def make(*a, **kw):
                    nonlocal inner, args, kwargs
                    return inner(*args, *a, **(kwargs | kw))

                return make

        else:
            def resolver(scp: "Scope", token):
                nonlocal dep
                return scp[dep]

        return resolver, {dep}



@export()
class DepProvider(Alias):
    
    # static: t.ClassVar[bool] = True

    def _bind(self, injector: "Injector", token: Dep):

        dep = token.__dependency__
        scope = token.__scope__
        default = token.__default__

        if not scope is None:
            if not (scope == injector or scope in injector.containers):
                return None, None
        
        if default is _EMPTY:
            return lambda ctx, d: ctx[dep], {dep}
        else:
            fb = lambda: default
            return lambda ctx, d: ctx.get(dep, fb), {dep}


@export()
class LookupProvider(Alias):

    def _bind(self, injector: "Injector", token: "InjectedLookup") -> Handler:

        dep = token.depends
        path = token.path

        def hander(scp: "Scope", token):
            nonlocal dep, path
            var = scp[dep]
            return lambda: path.get(var())

        return hander, {dep}


@export()
class Factory(Provider[Callable[..., T_Injected], T_Injected]):

    arguments: Arguments = _Attr(default_factory=Arguments)
    is_singleton: bool = False
    is_partial: bool = False

    decorators: list[Callable[[Callable], Callable]] = _Attr(default_factory=list)

    deps: dict[str, Injectable] = _Attr(default_factory=frozendict)

    _resolver_class: t.ClassVar[type[FactoryResolver]] = FactoryResolver

    def __init__(
        self,
        provide: Injectable = ...,
        using: Callable[..., T_Injectable] = ...,
        /,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(
            Missing if provide in (None, ...) else provide,
            Missing if using in (None, ...) else using,
        )

        args and self.args(*args)
        kwargs and self.kwargs(**kwargs)

    def _uses_fallback(self):
        if callable(self._provides):
            return self._provides

        return super()._uses_fallback()

    def _provides_fallback(self):
        if isinstance(self._uses, Injectable):
            return self._uses
        return super()._provides_fallback()

    def depends(self, **deps) -> Self:
        self.__set_attr("deps", frozendict(deps))
        return self

    def args(self, *args) -> Self:
        self.__set_attr("arguments", self.arguments.replace(args))
        return self

    def kwargs(self, **kwargs) -> Self:
        self.__set_attr("arguments", self.arguments.replace(kwargs=kwargs))
        return self

    def singleton(self, is_singleton: bool = True) -> Self:
        self.__set_attr("is_singleton", is_singleton)
        return self
    
    def decorate(self, *decorators: Callable[[Callable], Callable]) -> Self:
        self.decorators.extend(decorators)
        return self

    def _iter_decorators(self):
        yield from self.decorators
        if self.is_singleton:
            yield singleton_decorator

    def _bind(self, injector: "Injector", token: T_Injectable) -> Handler:
        return self._resolver_class(
                    self.uses, 
                    arguments=self.arguments, 
                    decorators=self._iter_decorators()
                )(injector, token)



@export()
class Function(Factory[T_Injected]):
    ...


@export()
class Type(Factory[T_Injected]):
    ...


@export()
class InjectionProvider(Factory[T_Injected]):

    is_partial: bool = True

    _wrapper: Callable

    _resolver_class: t.ClassVar[type[PartialFactoryResolver]] = PartialFactoryResolver

    @property
    def wrapped(self):
        return self.uses

    @property
    @cache
    def wrapper(self):
        try:
            return self._wrapper
        except AttributeError:
            self.__set_attr("_wrapper", self._make_wrapper())
            return self._wrapper

    def _make_wrapper(self):
        wrapped = self.wrapped

        @wraps(wrapped)
        def wrapper(*a, **kw):
            nonlocal self, wrapped
            return self.container._context()[wrapped](*a, **kw)

        wrapper.__injects__ = wrapped
        return wrapper
    
    

def _provder_factory_method(cls: type[_T]):
    @wraps(cls)
    def wrapper(self: "RegistrarMixin", *a, **kw) -> type[_T]:
        val = cls(*a, **kw)
        self.register_provider(val)
        return val

    return t.cast(cls, wrapper)


@export()
class RegistrarMixin(ABC, t.Generic[T_Injected]):

    __slots__ = ()

    @abstractmethod
    def register_provider(self, provider: Provider[T_UsingAny, T_Injected]) -> Self:
        ...

    def alias(self, *a, **kw) -> Alias:
        ...

    def value(self, *a, **kw) -> Value:
        ...

    def factory(self, *a, **kw) -> Factory:
        ...

    def function(self, *a, **kw) -> Function:
        ...

    def type(self, *a, **kw) -> Type:
        ...

    if t.TYPE_CHECKING:
        alias = Alias
        value = Value
        factory = Factory
        function = Function
        type = Type
    else:
        alias = _provder_factory_method(Alias)
        value = _provder_factory_method(Value)
        factory = _provder_factory_method(Factory)
        function = _provder_factory_method(Function)
        type = _provder_factory_method(Type)

    def inject(self, func: Callable[..., _T] = None, **opts):
        def decorator(fn: Callable[..., _T]):
            pro = InjectionProvider(fn)
            self.register_provider(pro)
            return pro.wrapper

        if func is None:
            return decorator
        else:
            return decorator(func)
