from logging import getLogger
import typing as t



from laza.common.functools import cached_property, export


from . import providers as p
from .common import (
    Injectable,
    T_Injectable,
)

from .exc import DuplicateProviderError




logger = getLogger(__name__)


ProviderDict = dict[T_Injectable, p.Provider]



@export()
class ProviderRegistry:

    @cached_property(lambda s: ProviderDict(), readonly=True).getter
    def registry(self) -> ProviderDict:
        return self._create_registry()

    @property
    def repository(self):
        return self.registry

    def __bool__(self):
        return True
   
    def __len__(self):
        return len(self.repository)
    
    def __contains__(self, x):
        return x in self.repository
    
    def __delitem__(self, key: Injectable):
        if not self.unprovide(key):
            raise KeyError(key)

    def __getitem__(self, key: Injectable):
        try:
            return self.repository[key]
        except KeyError:
            return None

    def __setitem__(self, key: Injectable, value: p.Provider):
        return self.provide(key, value)

    def get(self, key, default=None):
        return self.repository.get(key, default)

    def setdefault(self, key: Injectable, value: p.Provider=None):
        return self.provide(key, value, default=True)

    def flush(self, tag: T_Injectable):
        ...
    
    def _create_registry(self) -> ProviderDict:
        return dict()

    def provide(self, 
            provide: t.Union[T_Injectable, None] , /,
            use: t.Union[p.Provider, p.T_UsingAny], 
            default: bool=None,
            **kwds):

        provider = self.create_provider(provide, use, **kwds)

        if provide is None:
            provide = provider.implicit_token()
            if provide is NotImplemented:
                raise ValueError(f'no implicit tag for {provider!r}')

        if not isinstance(provide, Injectable):
            raise TypeError(f'injector tag must be Injectable not {provide.__class__.__name__}: {provide}')

        original = self.registry.setdefault(provide, provider)
        if original is not provider:
            if default is True:
                return original
            raise DuplicateProviderError(f'{provide!r} {provider=!r}, {original=!r}')
        self.flush(provide)
        return provider
        
    def unprovide(self, 
            tag: Injectable, /,
            uses: t.Union[p.Provider, p.T_UsingAny]=None):

        registry = self.registry
        if tag in registry:
            if uses in (None, (p := registry[tag]), p.target):
                del registry[tag]
                self.flush(tag)
                return True
        
        return False
            
    def create_provider(self, provide, use: t.Union[p.Provider, p.T_UsingAny], **kwds: dict) -> p.Provider:
        if isinstance(use, p.Provider):
            if kwds:
                raise ValueError(f'got unexpected keyword arguments {tuple(kwds)}')
            return use

        cls = self._get_provider_class(provide, use, kwds)
        return cls(use, **kwds)

    def _get_provider_class(self, provide, use, kwds: dict) -> type[p.Provider]:
        raise LookupError(f'unkown provider: {provide=} {use=}')

    def alias(self, provide: T_Injectable, use: T_Injectable=None, **kwds):
        """Registers an `Alias provider`
        """
        def register(use_):
            self.provide(provide, p.AliasProvider(use_, **kwds))
            return use_
        
        if use is None:
            return register
        else:
            return register(use) 

    def value(self, provide: T_Injectable, use: p.T_UsingValue, **kwds):
        """Registers an `Value provider`
        """
        self.provide(provide, p.ValueProvider(use, **kwds))
        return use

    def function(self, use: type[T_Injectable]=None, /, provide: T_Injectable=None, **kwds):
        def register(use_):
            self.provide(provide, p.FunctionProvider(use_, **kwds))
            return use_
        if use is None:
            return register
        else:
            return register(use)    
   
    def type(self, use: type[T_Injectable]=None, /, provide: T_Injectable=None, **kwds):
        def register(use_):
            self.provide(provide, p.TypeProvider(use_, **kwds))
            return use_
        
        if use is None:
            return register
        else:
            return register(use)    
   
    def factory(self, provide: T_Injectable, use: p.T_UsingFactory =None, **kwds):
        def register(use_):
            self.provide(provide, p.FactoryProvider(use_, **kwds))
            return use_

        if use is None:
            return register
        else:
            return register(use)    
  
   