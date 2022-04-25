import sys
import typing as t
from abc import ABC, abstractmethod
from collections import abc
from functools import wraps
from inspect import Parameter, Signature, iscoroutinefunction
from logging import getLogger
from types import FunctionType, GenericAlias

import attr
from typing_extensions import Self

from ._common import lookups

from . import _dependency as dependency
from ._common import Missing, FrozenDict, private_setattr, typed_signature
from ._functools import BoundParams
from .core import Injectable, T_Injectable, T_Injected, is_injectable
from .makers import Dep, DependencyMarker, Lookup, PureDep

if sys.version_info < (3, 10):  # pragma: py-gt-39
    _UnionType = type(t.Union[t.Any, None])
else:                           # pragma: py-lt-310
    from types import UnionType as _UnionType

_AnnotatedType = type(t.Annotated[t.Any, 'ann'])



if t.TYPE_CHECKING:  # pragma: no cover
    from .containers import Container
    from .scopes import Injector, Scope




logger = getLogger(__name__)


_T = t.TypeVar("_T")
_T_Fn = t.TypeVar("_T_Fn", bound=abc.Callable, covariant=True)

_T_Concrete = t.TypeVar("_T_Concrete")
"""Provider's `concrete` `TypeVar`"""

_T_Binding = t.TypeVar('_T_Binding', bound=dependency.Dependency, covariant=True)
"""Dependency `TypeVar`"""



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





@DependencyMarker.register
@private_setattr(frozen='_frozen')
@attr.s(slots=True, frozen=True, cache_hash=True, cmp=True)
class Provider(t.Generic[_T_Concrete, _T_Binding]):
    """The base class for all providers.

    Subclasses can implement the `_resolve()` method to return the appropriate
    `Dependency` object for any given dependency. Also, conditional providers can
    implement the `_can_resolve()' method which should return `True` when the 
    provider can resolve or `False` if otherwise.
    
    Attributes:
        concrete (Any): The object used to resolve 
        container (Container): The Container where this provider is defined.
        is_default (bool): Whether this provider is the default. 
            A default provider only gets used if none other was provided to override it.
        is_async (bool): Whether this provider is asyncnous
        filters (tuple[Callable]): Called to determine whether this provider can be resolved.

    """


    _frozen: bool = attr.ib(init=False, cmp=False, default=False)

    concrete: _T_Concrete = attr.ib(default=Missing)
    container: "Container" = attr.ib(kw_only=True, default=None) 

    is_default: bool = attr.ib(kw_only=True, default=False)
    
    is_async: bool = attr.ib(init=False, default=None)
    
    filters: tuple[abc.Callable[['Scope', Injectable], bool]] = attr.ib(kw_only=True, default=(), converter=tuple)
    
    _dependency_class: t.ClassVar[type[_T_Binding]] = None
    _dependency_kwargs: t.ClassVar = {}

    __class_getitem__ = classmethod(GenericAlias)

    def default(self, is_default: bool = True) -> Self:
        """_Mark/Unmark_ this provider as the default. Updates the provider's 
        `is_default` attribute.
        
        A default provider will be skipped if the dependency they provide has 
        another provider. This means that a default provider will only get used 
        if no other providers for the given dependency were defined in the current scope.

        Args:
            is_default (bool, optional): `True` to _mark_ or `False` to _unmark_. 
                Defaults to `True`.
        Returns:
            self (Provider): this provider
        """
        self.__setattr(is_default=is_default)
        return self


    def can_resolve(self, abstract: T_Injectable, scope: "Scope") -> bool:
        """Check if this provider can resolve the given dependency in the given 
        scope.

        Used internally by the `resolve` method.

        Runs the provider's `filters` and if any of them fails (returns `False`), 
        this method will return `False`.
        
        Args:
            abstract (T_Injectable): dependency to be resolved
            scope (Scope): Scope within which the dependency is getting resolved.

        Returns:
            bool: `True` if dependency can be resolved or `False` if otherwise.
        """
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

    def resolve(self, abstract: T_Injectable, scope: 'Scope') -> _T_Binding:
        """Resolve the given dependency.

        Used internally by `Scope`

        Args:
            abstract (T_Injectable): dependency to be resolved 
            scope (Scope): Scope within which the dependency is getting resolved.

        Returns:
            dependency (Optional[Dependency]):
        """
        self._freeze()
        if self.can_resolve(abstract, scope):
            return self._resolve(abstract, scope)

    def _resolve(self, abstract: T_Injectable, scope: 'Scope') -> _T_Binding:
        return self._make_dependency(abstract, scope)

    def set_container(self, container: "Container") -> Self:
        """Sets the provide's container

        Args:
            container (Container): _description_

        Raises:
            AttributeError: When another container was already set

        Returns:
            self (Provider): this provider
        """
        if not self.container is None:
            if not container is self.container:
                raise AttributeError(
                    f"container for `{self}` already set to `{self.container}`."
                )
        else:
            self.__setattr(container=container)
        return self
   
    @t.overload
    def use(self) -> abc.Callable[[_T], _T]: ...
    @t.overload
    def use(self, using: t.Any) -> Self: ...
    @_fluent_decorator()
    def use(self, using: _T_Concrete) -> Self:
        """Set the provider's `concrete` attribute. 

        The given value will depend on the type of provider
        
        Can be used as decorator
                        
            @provider.use()
            def func(): 
                ...

        Args:
            using (_T_Concrete): the object to provide. this depends on the type 
                of provider

        Returns:
            self (Provider): this provider

        """
        self.__setattr(concrete=using)
        return self

    def when(self, *filters: abc.Callable, replace: bool=False) -> Self:
        """Add/replace the provider's `filters`. 

        Filters are callables that determine whether this provider can provide a
        given dependency.
        
        Filters are called with 3 arguments. Namely: `provider`- this provide, 
        `abstract` - the dependency to be provided
        and `scope`- scope within which the dependency is getting resolved.

        Args:
            *filters (Callable): The filter callables.
            replace (bool, optional): Whether to replace the existing filters 
                instead of adding. Defaults to False.

        Returns:
            self (Provider): this provider
        """
        if replace:
            self.__setattr(filters=tuple(dict.fromkeys(filters)))
        else:
            self.__setattr(filters=tuple(dict.fromkeys(self.filters + filters)))
        return self

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






@attr.s(slots=True, frozen=True)
class Alias(Provider[T_Injectable, _T_Binding]):
    """Used to proxy another existing dependency. It resolves to the given `concrete`.
    
    For example. To use `_Ta` for dependency `_Tb`.

        container[_Tb] = Alias(_Ta)

    Args:
        concrete (Injectable): The dependency to be proxied
    """

    def _resolve(self, abstract: T_Injectable, scope: 'Scope'):
        return scope[self.concrete]
  
  


@attr.s(slots=True, frozen=True)
class Value(Provider[T_Injected, dependency.Value]):
    """Provides the given object as it is. 

    Example:
        `T` will always resolve to `obj`.
            
            obj = object()
            container[T] = Value(obj)

    Args:
        concrete (T_Injected): The object to be provided
    """

    _dependency_class = dependency.Value

    def _get_dependency_kwargs(self, **kwds):
        kwds.setdefault('concrete', self.concrete)
        return super()._get_dependency_kwargs(**kwds)




_T_FactoryBinding = t.TypeVar('_T_FactoryBinding', bound=dependency.Factory, covariant=True)
"""Factory dependency `TypeVar`"""

@attr.s(slots=True, cmp=True, init=False, frozen=True)
class Factory(Provider[abc.Callable[..., T_Injected], _T_FactoryBinding], t.Generic[T_Injected, _T_FactoryBinding]):
    """Resolves to the return value of the given factory. A factory can be a 
    `type`, `function` or a `Callable` object. 

    The factory is called every time a dependency for this provider is requested.
    
    Attributes:
        concrete (Union[type[T_Injected], abc.Callable[..., T_Injected]]): the factory to used
            to create the provided value. 
        arguments (tuple[tuple. frozendict]): A tuple of positional and keyword 
            arguments passed to the factory.

    Params:
        concrete (Union[type[T_Injected], abc.Callable[..., T_Injected]], optional): 
            the factory. Can be a `type`, `function` or a `Callable` object.
        *args (Union[Dep, Any], optional): Positional arguments to pass to the factory.
        **kwargs (Union[Dep, Any], optional): Keyword arguments to pass to the factory.

    !!! note ""
        ## With Arguments
        
        Positional and/or keyword arguments to pass to the factory may be provided.

        ### Values Only
           
        ```python linenums="1" hl_lines="0"
        Factory(func, 'a', 32, obj, key='xyz')
        # will call: func('a', 32, obj, key='xyz')
        ```

        ### Values and Dependencies

        Arguments of type [`DependencyMarker`](../makers/#xdi.makers.DependencyMarker) 
        will automatically be resolved and passed to the factory while calling it. 
        
        e.g. using [`Dep`](../makers/#xdi.makers.Dep) and 
        [`Lookup`](../makers/#xdi.makers.Lookup):
        ```python linenums="1" hl_lines="4 7"
        Factory(
            func, 
            'a', 
            xdi.makers.Dep(Foo), 
            obj, 
            key='xyz', 
            bar=xdi.makers.Lookup(FooBar).bar
        )
        # will call: func('a', <inject: Foo>, obj, key='xyz', bar=<inject: FooBar>.bar)
        ```


    """
    arguments: tuple[tuple, FrozenDict] = attr.ib(default=((), FrozenDict()))
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

    def __init__(self, concrete: abc.Callable[[], T_Injectable] = None, /, *args, **kwargs):
        self.__attrs_init__(
            concrete=concrete, 
            arguments=(args, FrozenDict(kwargs))
        )

    def asynchronous(self, is_async: bool=True) -> Self:
        """_Mark/Unmark_ this provider as asynchronous. Updates `is_async`
        attribute.

        Normally, `coroutines` and factories with `async` dependencies automatically
        detected as asynchronous. This method provides the ability to change this
        default behaviour.

        Args:
            is_async (Union[bool, None], optional): `True` to _mark_, `False` 
                to _unmark_ or `None` to revert to the default behaviour. 
                Defaults to `True`.
        Returns:
            self (Provider): this provider
        """

        self.__setattr(is_async=is_async)
        return self

    def args(self, *args) -> Self:
        """Set the positional arguments to pass to the factory. 

        Updates the `arguments` attribute.

        Args:
            *args (Union[Dep, Any], optional): Positional arguments to pass to 
                the factory.

        Returns:
            self (Provider): this provider

        """
        arguments = self.arguments
        self.__setattr(arguments=(args, *arguments[1:]))
        return self

    def kwargs(self, **kwargs) -> Self:
        """Set the keyword arguments to pass to the factory. 

        Updates the `arguments` attribute.

        Args:
            **kwargs (Union[Dep, Any], optional): Keyword arguments to pass to 
                the factory.

        Returns:
            self (Provider): this provider
        """
        arguments = self.arguments
        self.__setattr(arguments=(*arguments[:1], FrozenDict(kwargs)))
        return self
 
    @t.overload
    def use(self) -> abc.Callable[[_T], _T]: ...

    @t.overload
    def use(self, using: abc.Callable, *args, **kwargs) -> Self: ...

    @_fluent_decorator()
    def use(self, concrete, *args, **kwargs):
        """Sets the provider's factory and arguments.
        
        Params:
            concrete (Union[type[T_Injected], abc.Callable[..., T_Injected]], optional): 
                the factory. Can be a `type`, `function` or a `Callable` object.
            *args (Union[Dep, Any], optional): Positional arguments to pass to the factory.
            **kwargs (Union[Dep, Any], optional): Keyword arguments to pass to the factory.

        Returns:
            self (Factory): this provider
        """
        self.__setattr(concrete=concrete)
        args and self.args(*args)
        kwargs and self.kwargs(**kwargs)
        return self
        
    def signature(self, signature: Signature) -> Self:
        """Set a custom `Signature` for the factory.

        Args:
            signature (Signature): the signature

        Returns:
            self (Factory): this provider
        """
        self.__setattr(_signature=signature)
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
        

_T_SingletonBinding = t.TypeVar('_T_SingletonBinding', bound=dependency.Singleton, covariant=True)
"""Singleton dependency `TypeVar`"""

@attr.s(slots=True, cmp=True, init=False)
class Singleton(Factory[T_Injected, _T_SingletonBinding]):
    """A `Singleton` provider is a `Factory` that returns same instance on every
    call.

    On the first request, the given factory will be called to create the instance 
    which will be stored and returned on subsequent requests.

    Attributes:
        is_thread_safe (bool): Indicates whether to wrap the factory call with a
            `Lock` to prevent simultaneous instance create when injecting from 
            multiple threads. Defaults to None
    """

    is_shared: t.ClassVar[bool] = True
    is_thread_safe: bool = attr.ib(init=False, default=None)

    _sync_dependency_class: t.ClassVar = dependency.Singleton
    _async_dependency_class: t.ClassVar = dependency.AsyncSingleton
    _await_params_sync_dependency_class: t.ClassVar = dependency.AwaitParamsSingleton
    _await_params_async_dependency_class: t.ClassVar = dependency.AwaitParamsAsyncSingleton

    def thread_safe(self, is_thread_safe: bool=True) -> Self:
        """_Mark/Unmark_ this provider as thread safe. Updates the `is_thread_safe`
        attribute.
        
        `is_thread_safe` indicates whether to wrap the factory call with a `Lock` 
        to prevent simultaneous instance create when injecting from multiple threads.

        Args:
            is_thread_safe (bool, optional): `True` to _mark_ or `False` to 
                _unmark_. Defaults to True.

        Returns:
            self (Provider): this provider
        """
        self.__setattr(is_thread_safe=is_thread_safe)
        return self

    def _get_dependency_kwargs(self, **kwds):
        kwds.setdefault('thread_safe', self.is_thread_safe)
        return super()._get_dependency_kwargs(**kwds)





_T_ResourceBinding = t.TypeVar('_T_ResourceBinding', bound=dependency.Singleton, covariant=True)
"""Resource dependency `TypeVar`"""


@attr.s(slots=True, cmp=True, init=False)
class Resource(Singleton[T_Injected, _T_ResourceBinding]):
    """A `Resource` provider is a `Singleton` that has initialization and/or 
    teardown.
    
    """

    is_async: bool = attr.ib(init=False, default=None)
    is_awaitable: bool = attr.ib(init=False, default=None)
    is_shared: t.ClassVar[bool] = True

    def awaitable(self, is_awaitable=True):
        self.__setattr(is_awaitable=is_awaitable)
        return self
        
    def _get_dependency_kwargs(self, **kwds):
        # kwds.setdefault('aw_enter', self.is_awaitable)
        return super()._get_dependency_kwargs(**kwds)



_T_PartialBinding  = t.TypeVar('_T_PartialBinding', bound=dependency.Partial, covariant=True)
"""Partial dependency `TypeVar`"""



@attr.s(slots=True, init=False)
class Partial(Factory[T_Injected, _T_PartialBinding]):
    """A `Factory` provider that accepts extra arguments during resolution.

    Used internally to inject entry-point functions.
    """

    _sync_dependency_class: t.ClassVar = dependency.Partial
    _async_dependency_class: t.ClassVar = dependency.AsyncPartial
    _await_params_sync_dependency_class: t.ClassVar = dependency.AwaitParamsPartial
    _await_params_async_dependency_class: t.ClassVar = dependency.AwaitParamsAsyncPartial

    def _fallback_signature(self):
        return self._arbitrary_signature





_T_CallableBinding = t.TypeVar('_T_CallableBinding', bound=dependency.Callable, covariant=True)
"""Callable dependency `TypeVar`"""


@attr.s(slots=True, init=False)
class Callable(Partial[T_Injected, _T_CallableBinding]):
    """Similar to a `Factory` provider, a `Callable` provider resolves to a 
    callable that wraps the factory.
    
    """

    _sync_dependency_class: t.ClassVar = dependency.Callable
    _async_dependency_class: t.ClassVar = dependency.AsyncCallable
    _await_params_sync_dependency_class: t.ClassVar = dependency.AwaitParamsCallable
    _await_params_async_dependency_class: t.ClassVar = dependency.AwaitParamsAsyncCallable






@attr.s(slots=True, frozen=True)
class LookupMarkerProvider(Factory[lookups.look, _T_FactoryBinding]):
    """Provider for resolving `xdi.Lookup` dependencies. 
    """
    
    abstract = Lookup
    concrete = attr.ib(init=False, default=lookups.look)

    def _can_resolve(self, abstract: T_Injectable, scope: "Scope") -> bool:
        return isinstance(abstract, Lookup)

    def _bind_params(self, scope: "Scope", marker: Lookup, *, sig=None, arguments=()):
        if not arguments:
            abstract = marker.__abstract__
            arguments = (lookups.Lookup(*marker),), FrozenDict(root=Dep(abstract))
        return super()._bind_params(scope, marker, sig=sig, arguments=arguments)



@attr.s(slots=True, frozen=True)
class UnionProvider(Provider[_T_Concrete]):
    """Provider for resolving `Union` dependencies. 
    """

    abstract = t.get_origin(t.Union[t.Any, None])
    concrete = attr.ib(init=False, default=_UnionType)

    def get_all_args(self, abstract: Injectable):
        return t.get_args(abstract)

    def get_injectable_args(self, abstract: Injectable):
        return filter(is_injectable, self.get_all_args(abstract))

    def _resolve(self, abstract: T_Injectable, scope: 'Scope'):
        for arg in self.get_injectable_args(abstract):
            if rv := scope[arg]:
                return rv

    # def _can_resolve(self, abstract: T_Injectable, scope: "Scope") -> bool:
    #     assert isinstance(abstract, self.concrete)



@attr.s(slots=True, frozen=True)
class AnnotationProvider(UnionProvider[_T_Concrete]):
    """Annotated types provider
    """
    abstract = t.get_origin(t.Annotated[t.Any, None])
    concrete = attr.ib(init=False, default=_AnnotatedType)

    def get_all_args(self, abstract: t.Annotated):
        for a in abstract.__metadata__[::-1]:
            if isinstance(a, DependencyMarker):
                yield a
        yield abstract.__origin__

  



@attr.s(slots=True, frozen=True)
class DepMarkerProvider(Provider[_T_Concrete]):
    """Provider for resolving `zdi.Dep` dependencies. 
    """
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








_T_Fn = t.TypeVar('_T_Fn', bound=abc.Callable)




 
    

def _provder_factory_method(cls: _T_Fn) -> _T_Fn:
    @wraps(cls)
    def wrapper(self: "AbstractProviderRegistry", abstract, *a, **kw):
        if not a:
            a = abstract,
        self[abstract] = pro = cls(*a, **kw)
        return pro
    return t.cast(cls, wrapper)



class AbstractProviderRegistry(ABC):
    """Implements a collection of helper methods for creating providers.

    Subclassed by `Container` to provide these methods
    """
    __slots__ = ()

    @abstractmethod
    def __setitem__(self, abstract: Injectable, provider: Provider): # pragma: no cover
        ...

    def provide(self, *providers: t.Union[Provider, type, t.TypeVar, abc.Callable], **kwds) -> Self:
        for provider in providers:
            if isinstance(provider, tuple):
                abstract, provider = provider
            else:
                abstract, provider = provider, provider

            if isinstance(provider, Provider):
                if abstract == provider:
                    abstract = getattr(provider, 'abstract', abstract)
                self[abstract] = provider
            elif isinstance(provider, (type, GenericAlias, FunctionType)):
                self.factory(abstract, provider, **kwds)
            elif abstract != provider:
                self.value(abstract, provider, **kwds)
            else:
                raise ValueError(
                    f'providers must be of type `Provider`, `type`, '
                    f'`FunctionType` not {provider.__class__.__name__}'
                )
        return self
    
    if t.TYPE_CHECKING: # pragma: no cover

        def alias(self, abstract: Injectable, alias: t.Any, *a, **kw) -> Alias:
            ...

        def value(self, abstract: Injectable, value: t.Any, *a, **kw) -> Value:
            ...

        def callable(self, abstract: Injectable, factory: _T_Fn=...,  *a, **kw) -> Callable:
            ...

        def factory(self, abstract: Injectable, factory: _T_Fn=...,  *a, **kw) -> Factory:
            ...

        def resource(self, abstract: Injectable, factory: _T_Fn=...,  *a, **kw) -> Resource:
            ...
            
        def singleton(self, abstract: Injectable, factory: _T_Fn=...,  *a, **kw) -> Singleton:
            ...
            
    alias = _provder_factory_method(Alias)
    value = _provder_factory_method(Value)
    callable = _provder_factory_method(Callable)
    factory = _provder_factory_method(Factory)
    resource = _provder_factory_method(Resource)
    singleton = _provder_factory_method(Singleton)
