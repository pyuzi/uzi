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
    def wrapper(self: "ProviderRegistry", abstract, *a, **kw):
        self[abstract] = pro = cls(*a, **kw)
        return pro

    return t.cast(cls, wrapper)



class ProviderRegistry(ABC):

    __slots__ = ()

    @abstractmethod
    def __setitem__(self, abstract: Injectable, provider: Provider):
        ...

    def provide(self, *providers: t.Union[Provider, type, GenericAlias, FunctionType], **kwds) -> Self:
        for provider in providers:
            if isinstance(provider, tuple):
                abstract, provider = provider
            else:
                abstract, provider = provider, provider

            if isinstance(provider, Provider):
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
    
    if t.TYPE_CHECKING:

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
            
    else:
        alias = _provder_factory_method(Alias)
        value = _provder_factory_method(Value)
        callable = _provder_factory_method(Callable)
        factory = _provder_factory_method(Factory)
        resource = _provder_factory_method(Resource)
        singleton = _provder_factory_method(Singleton)
