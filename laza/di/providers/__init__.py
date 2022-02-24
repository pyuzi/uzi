# from __future__ import annotations
from inspect import ismemberdescriptor
from logging import getLogger
from types import GenericAlias
import typing as t
from functools import wraps
from inspect import Parameter
from abc import ABCMeta, abstractmethod
from laza.common.collections import Arguments, orderedset

from collections import ChainMap
from collections.abc import Callable, Set
from laza.common.typing import get_args, UnionType, Self, get_origin


from laza.common.functools import Missing, export


from laza.common.enum import BitSetFlag, auto

from laza.common.promises import Promise



from ..common import (
    Inject,
    InjectionMarker,
    InjectedLookup,
    Injectable,
    T_Injected,
    T_Injectable,
    isinjectable,
)
from .util import FactoryResolver, PartialFactoryResolver, singleton_decorator


if t.TYPE_CHECKING:
    from ..containers import Container
    from ..injectors import Injector, InjectorContext


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

TContextBinding =  Callable[['InjectorContext', t.Optional[Injectable]], Callable[..., T_Injected]]

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



@export()
class DuplicateProviderError(ValueError):
    pass




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


        slots = ns.get('__slots__', ()) 
        slots = slots + tuple(
            n for n, a in ann.items()
            if not n in slots and (get_origin(a) or a) not in (t.ClassVar, n in ns or t.Final)
        )

        ns["__slots__"] = slots
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


_missing_or_none = frozenset([Missing, None])

@export()
@InjectionMarker.register
class Provider(t.Generic[_T_Using, T_Injected], metaclass=ProviderType):

    __attr_defaults__: t.Final[dict[str, _Attr]] = ...

    _is_registered: bool = False

    __boot: Promise

    container: "Container" = None
    """The Container where this provider is setup.
    """

    autoloaded: bool = False

    is_default: bool = False
    """Whether this provider is the default. 
    A default provider only gets used if none other was provided to override it.
    """

    is_final: bool = False
    """Whether this provider is final. Final providers cannot be overridden 
    """

    _provides: T_Injectable = Missing
    """The Injectable/token provided by this provider
    """

    _uses: _T_Using = Missing
    """The object used to resolve 
    """

    filters: tuple[Callable[['Injector', Injectable], bool]] = ()
    """Called to determine whether this provider can be bound.
    """

    def __init__(self, provide: Injectable = Missing, using: Injectable = Missing) -> None:
        object.__setattr__(self, '_Provider__boot', Promise())
        # self.__boot.then(lambda: self._register())
        self.__init_attrs__()
        using in _missing_or_none or self.using(using)
        provide in _missing_or_none or self.provide(provide)

    @property
    def __dependency__(self):
        return self if self.container is None else self.provides

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
            self._register()
        elif val is not self._provides:
            raise AttributeError(
                f"cannot {val=}. {self} already provides {self._provides}."
            )

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
        self._is_registered or self._register()

    def _uses_fallback(self):
        return Missing

    def _provides_fallback(self):
        return Missing

    def set_container(self, container: "Container") -> Self:
        if not (self.container or container) is container:
            raise RuntimeError(
                f"container for `{self}` already set to `{self.container}`."
            )
        
        self.__set_attr("container", container)
        self._register()
        return self
   
    def _register(self):

        if self._is_registered is False:
            if self._prepare_to_register():
                self.container.add_to_registry(self.provides, self)
                self.__set_attr("_is_registered", True)
        else:
            raise TypeError(f'{self!s} already registered to {self.container}.')

    def _prepare_to_register(self):
        if not self.__boot.done():
            if self._is_registered:
                raise TypeError(f'{self!s} already registered to {self.container}.')
            try:
                if self._provides is Missing:
                    self.__set_attr("_provides", self.provides)
                if self._uses is Missing:
                    self.__set_attr("_uses", self.uses)
                return not self.container is None
            except AttributeError:
                return False
        return False
      
    def when(self, *filters, append: bool=False) -> Self:
        if append:
            self.__set_attr("filters", tuple(orderedset(self.filters + filters)))
        else:
            self.__set_attr("filters", tuple(orderedset(filters)))
        return self

    def autoload(self, autoloaded: bool = True) -> Self:
        self.__set_attr("autoloaded", autoloaded)
        return self

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

    def bind(self, injector: "Injector", provides: T_Injectable=None) -> 'TContextBinding':
        self.__boot.settle()
        if provides is None: provides = self.provides
        fn, deps = self._bind(injector, provides)
        return fn

    @abstractmethod
    def _bind(self, injector: "Injector", token: T_Injectable) -> tuple[Callable, Set]:
        ...

    def can_bind(self, injector: "Injector", dep: T_Injectable=None) -> bool:
        self.__boot.settle()
        if dep is None: 
            dep = self.provides
        
        if self.container is None or injector.is_scope(self.container):
            return self._can_bind(injector, dep) and self._run_filters(injector, dep)
        return False

    def _can_bind(self, injector: "Injector", dep: T_Injectable) -> bool:
        return True

    def _run_filters(self, injector: "Injector", dep: T_Injectable) -> bool:
        for fl in self.filters:
            if not fl(injector, dep):
                return False
        return True

    def substitute(self, *subs: 'Provider') -> 'Provider':
        if self.is_final:
            raise DuplicateProviderError(f'Final:{self} has duplicates: {[*subs]}')

        sub, *subs = subs
        return sub.substitute(*subs) if subs else sub

    def onboot(self, callback: t.Union[Promise, Callable]=None):
        return self.__boot.then(callback)

    def __init_attrs__(self):
        for k, attr in self.__attr_defaults__.items():
            self.__set_attr(k, attr(), force=True)

    def __str__(self):
        using = self._uses_fallback() if self._uses is Missing else self._uses
        return f"{self.__class__.__name__}({using})"

    def __repr__(self):
        using = self._uses_fallback() if self._uses is Missing else self._uses
        provides = (
            self._provides_fallback() if self._provides is Missing else self._provides
        )
        container = getattr(self, "container", None)
        container = container and container.name
        return f"{self.__class__.__name__}({provides=!r}, {using=!r}, {container=!r})"

    # @t.Final
    def __setattr__(self, name, value, *, force=False):
        if self.__boot.done():
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

    if t.TYPE_CHECKING:
        def __init__(self, provide: Injectable = Missing, value: T_Injected = Missing) -> None:
            ...

    def _bind(self, injector: "Injector", dep: T_Injectable) -> 'TContextBinding':
        value = self.uses
        func = lambda at, key=dep: lambda: value
        return func, None




@export()
class InjecorContextProvider(Provider[T_UsingValue, "Injector"]):
    """Provides given value as it is."""
    _uses = None

    def _provides_fallback(self):
        return self

    def _bind(self, injector: "Injector", dep: T_Injectable):
        return lambda ctx, key=dep: lambda: ctx, None




@export()
class Alias(Provider[T_UsingAlias, T_Injected]):


    if t.TYPE_CHECKING:
        def __init__(self, provide: Injectable = Missing, alias: Injectable = Missing) -> None:
            ...
        
    def _can_bind(self, injector: "Injector", obj: T_Injectable) -> bool:
        return obj != self.uses and injector.is_provided(self.uses)

    def _bind(self, injector: "Injector", obj: T_Injectable) -> 'TContextBinding':
        real = self.uses

        def resolver(at: "InjectorContext", dep: T_Injectable=obj):
            nonlocal real
            return at[real]

        return resolver, {real}



@export()
class UnionProvider(Provider[_T_Using, T_Injected]):

    _bind_type = UnionType 
    _uses = UnionType

    def _provides_fallback(self):
        return UnionType

    def get_all_args(self, token: Injectable):
        return get_args(token)

    def _iter_injectable(self, injector: 'Injector', token: Injectable) -> tuple[Injectable]:
        for a in self.get_all_args(token):
            if isinjectable(a) and injector.is_provided(a):
                yield a
                
    def _is_bind_type(self, obj: T_Injectable):
        return isinstance(obj, self._bind_type)

    def _can_bind(self, injector: "Injector", obj: T_Injectable) -> bool:
        return self._is_bind_type(obj) and next(self._iter_injectable(injector, obj), ...)

    def _bind(self, injector: "Injector", obj):
        if deps := [*self._iter_injectable(injector, obj)]:
            def resolver(scp: "InjectorContext", o=obj):
                nonlocal deps
                for dep in deps:
                    if not (fn := scp[dep]) is None:
                        return fn
            return resolver, {*deps}
        return None, None





@export()
class AnnotatedProvider(UnionProvider):

    _uses: t.Final = type(t.Annotated)
    _bind_type = type(t.Annotated[t.Any, 'ann']) 

    def get_all_args(self, token: Injectable):
        return token.__metadata__[::-1]
  
    def _provides_fallback(self):
        return t.Annotated




@export()
class InjectProvider(Provider[Inject, T_Injected]):
    
    _uses: t.Final = Inject
    
    def _provides_fallback(self):
        return Inject

    def _can_bind(self, injector: "Injector", obj: Inject) -> bool:
        return obj.__scope__ is None or injector.is_scope(obj.__scope__)

    def _bind(self, injector: "Injector", obj: Inject):

        dep = obj.__injects__
        scope = obj.__scope__

        if scope is None or injector.is_scope(scope):
                
            if obj.is_optional:

                default = obj.__default__
                if isinstance(default, InjectionMarker):
                    return lambda ctx, d=obj: ctx.get(dep) or ctx[default], {dep}
                else:
                    fd = lambda: default
                    return lambda ctx, d=obj: ctx.get(dep, fd), {dep}
            else:
                return lambda ctx, d=obj: ctx[dep], {dep}

        return None, {dep}




@export()
class LookupProvider(Provider[Inject, T_Injected]):

    def _bind(self, injector: "Injector", obj: "InjectedLookup") -> 'TContextBinding':

        dep = obj.depends
        path = obj.path

        def hander(scp: "InjectorContext", o=obj):
            nonlocal dep, path
            var = scp[dep]
            return lambda: path.get(var())

        return hander, {dep}



@export()
class Factory(Provider[Callable[..., T_Injected], T_Injected]):

    arguments: Arguments = _Attr(default_factory=Arguments)
    is_singleton: bool = False
    # is_partial: bool = False

    decorators: list[Callable[[Callable], Callable]] = _Attr(default_factory=list)

    _resolver_class: t.ClassVar[type[FactoryResolver]] = FactoryResolver

    def __init__(self, using: Callable[..., T_Injectable] = None, /, *args, **kwargs) -> None:
        super().__init__()
        using is None or self.using(using)
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

    def _bind(self, injector: "Injector", token: T_Injectable) -> 'TContextBinding':
        return self._resolver_class(
                    self.uses, 
                    arguments=self.arguments, 
                    decorators=self._iter_decorators()
                )(injector, token)




@export()
class PartialFactory(Factory[T_Injected]):

    _resolver_class: t.ClassVar[type[PartialFactoryResolver]] = PartialFactoryResolver

   