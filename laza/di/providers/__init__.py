from types import MethodType
import typing as t
from abc import ABCMeta, abstractmethod
from collections import ChainMap, abc
from collections.abc import Callable as AbstractCallable
from collections.abc import Set
from contextlib import AbstractContextManager
from functools import wraps
from inspect import Parameter, Signature, iscoroutinefunction, ismemberdescriptor
from logging import getLogger

from laza.common.collections import Arguments
from laza.common.functools import Missing, export
from laza.common.typing import (Self, UnionType, get_args, get_origin,
                                typed_signature)

from .. import (Call, Dep, Injectable, DepInjectorFlag, InjectionMarker, T_Injectable,
                T_Injected, is_injectable)
from .functools import (
    CallableFactoryBinding,
    FactoryBinding,
    ResourceFactoryBinding,
    SingletonFactoryBinding,
    decorators
)



if t.TYPE_CHECKING:
    from ..containers import Container
    from ..injectors import Injector, InjectorContext


logger = getLogger(__name__)


_T = t.TypeVar("_T")
_T_Fn = t.TypeVar("_T_Fn", bound=abc.Callable, covariant=True)
_T_Using = t.TypeVar("_T_Using")

_EMPTY = Parameter.empty

T_UsingAlias = T_Injectable
T_UsingVariant = T_Injectable
T_UsingValue = T_Injected

T_UsingFunc = abc.Callable[..., T_Injected]
T_UsingType = type[T_Injected]

T_UsingCallable = t.Union[T_UsingType, T_UsingFunc]


T_UsingAny = t.Union[T_UsingCallable, T_UsingAlias, T_UsingValue]

TContextBinding =  abc.Callable[['InjectorContext', t.Optional[Injectable]], abc.Callable[..., T_Injected]]


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



@export()
class DuplicateProviderError(ValueError):
    pass




class _Attr(t.Generic[_T]):

    __slots__ = (
        "default",
        "__call__",
    )

    def __new__(
        cls: type[Self], default: _T = ..., *, default_factory: abc.Callable[[], _T] = ...
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



@export()
@InjectionMarker.register
class Provider(t.Generic[_T_Using, T_Injected], metaclass=ProviderType):

    _frozen: bool = False

    __attr_defaults__: t.Final[dict[str, _Attr]] = ...

    _is_registered: bool = False

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

    is_shared: t.ClassVar[bool] = None
    """Whether this provided value is shared.
    """

    is_async: bool = None
    """Whether the value is provided async.
    """

    filters: tuple[abc.Callable[['Injector', Injectable], bool]] = ()
    """Called to determine whether this provider can be bound.
    """

    def __init__(self, provide: Injectable = Missing, using: Injectable = Missing) -> None:
        self.__init_attrs__()
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

    def bind(self, injector: "Injector", provides: T_Injectable=None) -> 'TContextBinding':
        self._freeze()

        if self.container is None or injector.is_scope(self.container):
            fn, deps = self._bind(injector, provides)
            return fn

    @abstractmethod
    def _bind(self, injector: "Injector", token: T_Injectable) -> tuple[abc.Callable, Set]:
        ...

    def can_bind(self, injector: "Injector", dep: T_Injectable=None) -> bool:
        self._freeze()
        if self.container is None or injector.is_scope(self.container):
            return self._can_bind(injector, dep) and self._run_filters(injector, dep)
        return False

    def _can_bind(self, injector: "Injector", dep: T_Injectable) -> bool:
        return True

    def _run_filters(self, injector: "Injector", dep: T_Injectable) -> bool:
        for fl in self.filters:
            if not fl(self, injector, dep):
                return False
        return True

    def substitute(self, *subs: 'Provider') -> 'Provider':
        if self.is_final:
            raise DuplicateProviderError(f'Final:{self} has duplicates: {[*subs]}')

        sub, *subs = subs
        return sub.substitute(*subs) if subs else sub

    def _freeze(self):
        self._frozen or (self._onfreeze(), self.__set_attr(_frozen=True))

    def _onfreeze(self):
        ...

    def __init_attrs__(self):
        for k, attr in self.__attr_defaults__.items():
            self.__set_attr(k, attr(), True)

    def __str__(self):
        using = self._uses_fallback() if self._uses is Missing else self._uses
        return f"{self.__class__.__name__}({using})"

    def __repr__(self):
        using = self._uses_fallback() if self._uses is Missing else self._uses
        provides = (
            self._provides_fallback() if self._provides is Missing else self._provides
        )
        container = self.container
        return f"{self.__class__.__name__}({provides=!r}, {using=!r}, {container=!r})"

    # @t.Final
    def __setattr__(self, name=None, value=None, force=False, /, **kw):
        
        name is None or (kw := {name: value})

        if force is False and self._frozen:
            raise AttributeError(f"`cannot set {tuple(kw)} on frozen {self}.")
        
        for k,v in kw.items():
            object.__setattr__(self, k, v)

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

    is_shared: t.ClassVar[bool] = True

    if t.TYPE_CHECKING:
        def __init__(self, provide: Injectable = Missing, value: T_Injected = Missing) -> None:
            ...

    def _bind(self, injector: "Injector", dep: T_Injectable) -> 'TContextBinding':
        value = self.uses
        def make():
            nonlocal value
            return value
        
        return lambda ctx: make, None



@export()
class ContextManagerProvider(Value):
    """Provides given value as it is."""

    def _bind(self, injector: "Injector", dep: T_Injectable) -> 'TContextBinding':
        cm = self.uses
        if not isinstance(cm, AbstractContextManager):
            raise TypeError(f'value must be a `ContextManager` not `{cm}`')
        
        return lambda ctx: decorators.contextmanager(cm, ctx), None




@export()
class InjectorContextProvider(Provider[T_UsingValue, T_Injected]):
    """Provides the current `InjectorContext`"""
    _uses: t.ClassVar = None
    uses: t.ClassVar = None

    def _bind(self, injector: "Injector", dep: T_Injectable) -> 'TContextBinding':
        def run(ctx: 'InjectorContext'):
            def make():
                nonlocal ctx
                return ctx
            make.is_async = False
            return make

        return run, None



@export()
class Alias(Provider[T_UsingAlias, T_Injected]):


    if t.TYPE_CHECKING:
        def __init__(self, provide: Injectable = Missing, alias: Injectable = Missing) -> None:
            ...
        
    def _can_bind(self, injector: "Injector", obj: T_Injectable) -> bool:
        return obj != self.uses and injector.is_provided(self.uses)

    def _bind(self, injector: "Injector", obj: T_Injectable) -> 'TContextBinding':
        real = self.uses
        return lambda ctx: ctx[real], {real}



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
            if is_injectable(a) and injector.is_provided(a):
                yield a
                
    def _is_bind_type(self, obj: T_Injectable):
        return isinstance(obj, self._bind_type)

    def _can_bind(self, injector: "Injector", obj: T_Injectable) -> bool:
        return self._is_bind_type(obj) and next(self._iter_injectable(injector, obj), ...)

    def _bind(self, injector: "Injector", obj):
        if deps := [*self._iter_injectable(injector, obj)]:
            return lambda ctx: ctx.find(*deps), {*deps}
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
class DepMarkerProvider(Provider):
    
    _uses: t.ClassVar = Dep

    def _provides_fallback(self):
        return self.uses

    def _can_bind(self, injector: "Injector", obj: Dep) -> bool:
        return isinstance(obj, self.uses) and ( 
                obj.__injector__ is None
                or obj.__injector__ in DepInjectorFlag
                or injector.is_scope(obj.__injector__)
            )

    def _bind(self, injector: "Injector", marker: Dep):
        dep = marker.__injects__
        flag = marker.__injector__
        default = marker.__default__
        if not (inject_default := isinstance(default, InjectionMarker)):
            default = marker.__hasdefault__ and (lambda: default) or None
            if default:
                default.is_async = False

        if flag is Dep.ONLY_SELF:
            def run(ctx: 'InjectorContext'):
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
            def run(ctx: 'InjectorContext'):
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
            def run(ctx: 'InjectorContext'):
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






@export()
class CallMarkerProvider(Provider):
    
    _uses: t.ClassVar = Call

    def _provides_fallback(self):
        return self.uses

    def _can_bind(self, injector: "Injector", obj: Dep) -> bool:
        return isinstance(obj, self.uses)

    def _bind(self, injector: "Injector", marker: Call):
        dep = marker.__injects__
        argv = marker.__arguments__

        if isinstance(dep, InjectionMarker):
            provider = Callable(
                lambda fn, *a, **kw: fn(*a, **kw), 
                dep, *argv.args, **argv.kwargs
            )
        else:
            provider = Callable(dep, *argv.args, **argv.kwargs)

        return provider.bind(injector, dep), None
        
        


_none_or_ellipsis = frozenset([None, ...])
@export()
class Factory(Provider[abc.Callable[..., T_Injected], T_Injected]):

    arguments: Arguments = _Attr(default_factory=Arguments)
    is_shared: t.ClassVar[bool] = False
    
    _signature: Signature = None
    _blank_signature: t.ClassVar[Signature] = Signature()
    _arbitrary_signature: t.ClassVar[Signature] = Signature([
        Parameter('__Parameter_var_positional', Parameter.VAR_POSITIONAL),
        Parameter('__Parameter_var_keyword', Parameter.VAR_KEYWORD),
    ])

    # decorators: tuple[abc.Callable[[abc.Callable], abc.Callable]] = ()
    # _all_decorators: tuple[abc.Callable[[abc.Callable], abc.Callable]]

    _binding_class: t.ClassVar[type[FactoryBinding]] = FactoryBinding

    def __init__(self, provide: abc.Callable[..., T_Injectable] = None, /, *args, **kwargs) -> None:
        super().__init__()
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
        self.__set_attr(arguments=self.arguments.replace(args))
        return self

    def kwargs(self, **kwargs) -> Self:
        self.__set_attr(arguments=self.arguments.replace(kwargs=kwargs))
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

    def get_signature(self):
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

    def _bind(self, injector: "Injector", token: T_Injectable) -> 'TContextBinding':
        return self._create_binding(injector), None

    def _create_binding(self, injector: "Injector"):
        return self._binding_class(
                injector,
                self.uses, 
                self.get_signature(),
                is_async=self.is_async,
                arguments=self.arguments, 
            )




@export()
class Singleton(Factory[T_Injected]):

    is_shared: t.ClassVar[bool] = True
    is_thread_safe: bool = True
    _binding_class: t.ClassVar[type[SingletonFactoryBinding]] = SingletonFactoryBinding

    def thread_safe(self, is_thread_safe=True):
        self.__set_attr(is_thread_safe=is_thread_safe)
        return self

    def _create_binding(self, injector: "Injector"):
        return self._binding_class(
                injector,
                self.uses, 
                self.get_signature(),
                is_async=self.is_async,
                arguments=self.arguments, 
                thread_safe=self.is_thread_safe
            )




@export()
class Resource(Singleton[T_Injected]):

    is_async: bool = None
    is_awaitable: bool = None
    is_shared: t.ClassVar[bool] = True

    _binding_class: t.ClassVar[type[ResourceFactoryBinding]] = ResourceFactoryBinding

    def awaitable(self, is_awaitable=True):
        self.__set_attr(is_awaitable=is_awaitable)
        return self
        
    def _create_binding(self, injector: "Injector"):
        return self._binding_class(
                injector,
                self.uses, 
                self.get_signature(),
                is_async=self.is_async,
                aw_enter=self.is_awaitable,
                arguments=self.arguments, 
            )


@export()
class Callable(Factory[T_Injected]):

    _binding_class: t.ClassVar[type[CallableFactoryBinding]] = CallableFactoryBinding

    def _fallback_signature(self):
        return self._arbitrary_signature

    def _create_binding(self, injector: "Injector"):
        return self._binding_class(
                injector,
                self.uses, 
                self.get_signature(),
                is_async=self.is_async,
                arguments=self.arguments, 
            )


