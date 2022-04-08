import logging
import typing as t
from abc import ABC, abstractmethod
from collections.abc import Callable as AbcCallable
from functools import wraps
from types import FunctionType, GenericAlias

from typing_extensions import Self

from .. import Injectable
from . import Alias, Callable, Factory, Provider, Resource, Singleton, Value



logger = logging.getLogger(__name__)

_T_Fn = t.TypeVar('_T_Fn', bound=AbcCallable)




 
    

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
    
    if t.TYPE_CHECKING:

        def alias(self, provide: Injectable, alias: t.Any, /) -> Alias:
            ...

        def value(self, provide: Injectable, value: t.Any, /) -> Value:
            ...

        def callable(self, factory: _T_Fn=...,  *a, **kw) -> Callable:
            ...

        def factory(self, factory: _T_Fn=...,  *a, **kw) -> Factory:
            ...

        def resource(self, factory: _T_Fn=...,  *a, **kw) -> Resource:
            ...
            
        def singleton(self, factory: _T_Fn=...,  *a, **kw) -> Singleton:
            ...
            
    else:
        alias = _provder_factory_method(Alias)
        value = _provder_factory_method(Value)
        callable = _provder_factory_method(Callable)
        factory = _provder_factory_method(Factory)
        resource = _provder_factory_method(Resource)
        singleton = _provder_factory_method(Singleton)
