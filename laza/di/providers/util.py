from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from functools import update_wrapper
from types import FunctionType, GenericAlias
import typing as t 
import logging
from functools import wraps
from collections.abc import Callable as AbcCallable, Sequence
from typing_extensions import Self


from laza.common.collections import MultiChainMap
from laza.common.typing import get_origin



from ..context import context_partial
from .. import InjectionMarker, Injectable
from . import Callable, ContextManagerProvider, Provider, Alias, Resource, Value, Factory

if t.TYPE_CHECKING:
    from ..injectors import Injector

logger = logging.getLogger(__name__)

_T_Fn = t.TypeVar('_T_Fn', bound=AbcCallable)





class ProviderResolver:

    __slots__ = '__injector',  '__registry', 

    __injector: 'Injector'
    __registry: MultiChainMap[Injectable, Provider]

    def __new__(cls, injecor: 'Injector', registry: MultiChainMap[Injectable, Provider]):
        self = object.__new__(cls)
        self.__injector = injecor
        self.__registry = registry
        return self
    
    def resolve(self, dep: Injectable) -> t.Union[Provider, None]:
        if isinstance(dep, InjectionMarker):
            dep = dep.__dependency__

        if isinstance(dep, Provider):
            return dep if dep.can_bind(self.__injector, dep) else None

        ls = self.__registry.get_all(dep)
        if ls is None:
            ls = (origin := get_origin(dep)) and self.__registry.get_all(origin)
            if ls is None:
                return None
        return self._reduce_providers(dep, ls[::-1])
    
    def _reduce_providers(self, obj: Injectable, stack: Sequence['Provider']):
        stack = [v for v in stack if v.can_bind(self.__injector, obj)]
        stack = [v for v in stack if not v.is_default] or stack
        if stack:
            top, *extra = stack
            if extra:
                top = top.substitute(*extra)
            return top            




class BindingsMap(dict[Injectable, t.Union[_T_Fn, None]], t.Generic[_T_Fn]):

    __slots__ = '__injector', '__resolver',

    __injector: 'Injector'
    __resolver: ProviderResolver

    def __init__(self, injector: 'Injector', resolver: ProviderResolver):
        self.__injector = injector
        self.__resolver = resolver

    def __missing__(self, key):
        p = self.__resolver.resolve(key)
        # We cache the result for next time. This is  aggressive because by this
        # time it is expected the the key is provided and will bind somewhere.
        return dict.setdefault(self, key, p and p.bind(self.__injector, key))
         
    def not_mutable(self, *a, **kw):
        raise TypeError(f'immutable type {self.__class__.__name__}')

    __delitem__ = __setitem__ = setdefault = \
        pop = popitem = update = clear = \
        copy = __copy__ = __reduce__ = __deepcopy__ = not_mutable
    del not_mutable



 
    

def _provder_factory_method(cls: _T_Fn) -> _T_Fn:
    @wraps(cls)
    def wrapper(self: "ProviderRegistry", *a, **kw):
        val = cls(*a, **kw)
        self.register(val)
        return val

    return t.cast(cls, wrapper)



class ProviderRegistry(ABC):

    __slots__ = ()

    @abstractmethod
    def register(self, provider: Provider) -> Self:
        ...


    def provide(self, *providers: t.Union[Provider, type, GenericAlias, FunctionType]) -> Self:
        for provider in providers:
            if isinstance(provider, Provider):
                self.register(provider)
            elif isinstance(provider, (type, GenericAlias, FunctionType)):
                self.factory(provider)
            else:
                raise ValueError(
                    f'providers must be of type `Provider`, `type`, '
                    f'`FunctionType` not {provider.__class__.__name__}'
                )
        return self

    def inject(self, func: _T_Fn) -> _T_Fn:
        provider = Callable(func)
        self.register(provider)
        return update_wrapper(context_partial(provider), func)
       
    
    if t.TYPE_CHECKING:

        def alias(self, provide: Injectable, alias: t.Any, /) -> Alias:
            ...

        def value(self, provide: Injectable, value: t.Any, /) -> Value:
            ...

        def contextmanager(self, provide: Injectable, cm: AbstractContextManager, /) -> ContextManagerProvider:
            ...

        def callable(self, factory: _T_Fn,  *a, **kw) -> Callable:
            ...

        def factory(self, factory: _T_Fn,  *a, **kw) -> Factory:
            ...

        def resource(self, factory: _T_Fn,  *a, **kw) -> Resource:
            ...
            
    else:
        alias = _provder_factory_method(Alias)
        value = _provder_factory_method(Value)
        callable = _provder_factory_method(Callable)
        contextmanager = _provder_factory_method(ContextManagerProvider)
        factory = _provder_factory_method(Factory)
        resource = _provder_factory_method(Resource)
