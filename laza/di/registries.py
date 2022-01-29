from logging import getLogger
import os
from types import GenericAlias
import typing as t

from collections.abc import Callable, Mapping, Set

from laza.common.typing import get_origin

from laza.common.functools import cached_property, export


from . import providers as p
from .common import (
    Injectable,
    ResolverFunc,
    T_Injectable,
    KindOfProvider,
)

from .exc import DuplicateProviderError




logger = getLogger(__name__)


ProviderDict = dict[T_Injectable, p.Provider]


class ResolverDict(dict[T_Injectable, ResolverFunc]):

    __slots__ = 'registry',
    registry: Mapping[T_Injectable, p.Provider]

    def __init__(self, registry: Mapping[T_Injectable, p.Provider]):
        self.registry = registry

    def __missing__(self, key):
        if pro := self.registry[key]:
            return self.setdefault(key, pro(self, key))
        elif origin := get_origin(key):
            if pro := self.registry[origin]:
                return self.setdefault(key, pro(self, key))



@export()
class ResolverRegistry:

    resolver_dict_class: t.ClassVar[type[ResolverDict]] = ResolverDict

    @cached_property
    def resolvers(self):
        return self._create_resolvers()

    def _create_resolvers(self):
        return self.resolver_dict_class(self)



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
        if not self.unregister(key):
            raise KeyError(key)

    def __getitem__(self, key: Injectable):
        try:
            return self.repository[key]
        except KeyError:
            return None

    def __setitem__(self, key: Injectable, value: p.Provider):
        return self.register(key, value)

    def get(self, key, default=None):
        return self.repository.get(key, default)

    def setdefault(self, key: Injectable, value: p.Provider=None):
        return self.register(key, value, default=True)

    def flush(self, tag: T_Injectable):
        ...
    
    def _create_registry(self) -> ProviderDict:
        return dict()

    def register(self, 
            provide: t.Union[T_Injectable, None] , /,
            use: t.Union[p.Provider, p.T_UsingAny], 
            default: bool=None,
            **kwds):
        provider = self.create_provider(use, **kwds)

        if provide is None:
            provide = provider.implicit_tag()
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
        
    def unregister(self, 
            tag: Injectable, /,
            uses: t.Union[p.Provider, p.T_UsingAny]=None):

        registry = self.registry
        if tag in registry:
            if uses in (None, (p := registry[tag]), p.target):
                del registry[tag]
                self.flush(tag)
                return True
        
        return False
            
    def create_provider(self, provider: t.Union[p.Provider, p.T_UsingAny], **kwds: dict) -> p.Provider:
        if isinstance(provider, p.Provider):
            if kwds:
                raise ValueError(f'got unexpected keyword arguments {tuple(kwds)}')
            return provider

        cls = self._get_provider_class(KindOfProvider(kwds.pop('kind')), kwds)
        return cls(provider, **kwds)

    def _get_provider_class(self, kind: KindOfProvider, kwds: dict) -> type[p.Provider]:
        return kind.default_impl

    @t.overload
    def alias(self, 
            tags: t.Union[T_Injectable, None], 
            use: p.T_UsingAlias, 
            *, 
            shared:bool=None, 
            **opts) -> T_Injectable:
        ...

    @t.overload
    def alias(self, 
            *, 
            use: p.T_UsingAlias, 
            shared:bool=None, 
            **opts) -> Callable[[T_Injectable], T_Injectable]:
        ...
    @t.overload
    def alias(self, 
            tags: t.Union[T_Injectable, None],
            *, 
            shared:bool=None, 
            **opts) -> Callable[[p.T_UsingAlias], p.T_UsingAlias]:
        ...

    def alias(self, tags: t.Union[T_Injectable, None]=..., use: p.T_UsingAlias=..., **kwds):
        """Registers an `AliasProvider`
        """
        def register(obj):
            if use is ...:
                tag, use_ = tags, obj
            else:
                tag, use_ = obj, use

            self.register(tag, use_, kind=KindOfProvider.alias, **kwds)
            return obj
    
        if tags is ... or use is ...:
            return register
        else:
            return register(tags)    


    @t.overload
    def value(self, 
            provide: T_Injectable, /,
            use: p.T_UsingValue, *, 
            shared:bool=None, 
            **opts) -> T_Injectable:
        ...
    @t.overload
    def value(self, 
            *, 
            use: p.T_UsingValue,
            shared:bool=None, 
            **opts) -> Callable[[T_Injectable], T_Injectable]:
        ...

    def value(self, provide:  t.Union[T_Injectable, None]=None, /, use: p.T_UsingValue=..., **kwds):
        """Registers an `AliasProvider`
        """
        def register(obj: T_Injectable):
            self.register(obj, use, kind=KindOfProvider.value, **kwds)

            return obj

        if provide is None:
            return register
        else:
            return register(provide)    

    @t.overload
    def function(self, 
            provide: t.Union[T_Injectable, None], /, 
            use: p.T_UsingFunc, *, 
            shared:bool=None, 
            **opts) -> T_Injectable:
        ...
    @t.overload
    def function(self, 
            *, 
            use: p.T_UsingFunc, 
            shared:bool=None, 
            **opts) -> Callable[[T_Injectable], T_Injectable]:
        ...

    @t.overload
    def function(self, 
            provide: t.Union[T_Injectable, None]=None, /, 
            *, 
            shared:bool=None, 
            **opts) -> Callable[[p.T_UsingFunc], p.T_UsingFunc]:
        ...

    def function(self, provide: t.Union[T_Injectable, None]=None, /, use: p.T_UsingFunc =..., **kwds):
        """Registers an `AliasProvider`
        """
        def register(obj):
            if use is ...:
                tag, use_ = provide, obj
            else:
                tag, use_ = obj, use

            self.register(tag, use_, kind=KindOfProvider.func, **kwds)
            return obj
    
        if provide is None or use is ...:
            return register
        else:
            return register(provide)    

    @t.overload
    def type(self, 
            provide: t.Union[T_Injectable, None], 
            /,
            use: p.T_UsingType, *, 
            shared:bool=None, 
            **opts) -> T_Injectable:
        ...

    @t.overload
    def type(self, *,
            use: p.T_UsingType, 
            shared:bool=None, 
            **opts) -> Callable[[T_Injectable], T_Injectable]:
        ...
    @t.overload
    def type(self, 
            provide: t.Union[T_Injectable, None]=None, 
            /, *, 
            shared:bool=None, 
            **opts) -> Callable[[p.T_UsingType], p.T_UsingType]:
        ...

    def type(self, provide: t.Union[T_Injectable, None]=None, /, use: p.T_UsingType =..., **kwds):
        def register(obj):
            if use is ...:
                tag, use_ = provide, obj
            else:
                tag, use_ = obj, use

            self.register(tag, use_, kind=KindOfProvider.type, **kwds)
            return obj
    
        if provide is None or use is ...:
            return register
        else:
            return register(provide)    
            
    @t.overload
    def injectable(self, 
                provide: t.Union[T_Injectable, None], /,
                use: p.T_UsingAny, 
                *,
                shared:bool=None, 
                **opts) -> T_Injectable:
        ...    
    @t.overload
    def injectable(self, 
                *,
                use: p.T_UsingAny, 
                shared:bool=None, 
                **opts) -> Callable[[T_Injectable], T_Injectable]:
        ...
    @t.overload
    def injectable(self, 
                provide: t.Union[T_Injectable, None]=None,
                 /, *,
                shared:bool=None, 
                **opts) -> Callable[[p.T_UsingAny], p.T_UsingAny]:
        ...

    def injectable(self, provide: t.Union[T_Injectable, None]=None, /, use: p.T_UsingAny =..., **kwds):
        def register(obj):
            if use is ...:
                tag, use_ = provide, obj
            else:
                tag, use_ = obj, use

            kind = kwds.pop('kind', None)
            if not kind:
                if not callable(use_):
                    raise TypeError(f'expected Callable but got {type(use_)} for {tag!r}')
                elif isinstance(use_, (type, GenericAlias)):
                    kind = KindOfProvider.type
                else:
                    kind = KindOfProvider.func

            self.register(tag, use_, kind=kind, **kwds)
            return obj
    
        if provide is None or use is ...:
            return register
        else:
            return register(provide)    

    @t.overload
    def provide(self, 
            tags: T_Injectable, 
            use: p.T_UsingFactory, 
            *, 
            shared:bool=None, 
            **opts) -> p.T_UsingFactory:
        ...
    @t.overload
    def provide(self, 
            tags: T_Injectable, 
            *, 
            shared:bool=None, 
            **opts) -> Callable[[p.T_UsingFactory], p.T_UsingFactory]:
        ...

    @t.overload
    def provide(self, *, 
            use: p.T_UsingFactory, 
            shared:bool=None, 
            **opts) -> Callable[[T_Injectable], T_Injectable]:
        ...

    def provide(self, provide: T_Injectable=..., use: p.T_UsingFactory =..., **kwds):
        def register(obj):
            if use is ...:
                tag, use_ = provide, obj
            else:
                tag, use_ = obj, use

            self.register(tag, use_, kind=KindOfProvider.factory, **kwds)
            return obj
    
        if provide is ... or use is ...:
            return register
        else:
            return register(provide)    

    @t.overload
    def resolver(self, 
            tags: T_Injectable, 
            use: p.T_UsingResolver, 
            *, 
            shared:bool=None, 
            **opts) -> p.T_UsingResolver:
        ...
    
    @t.overload
    def resolver(self, *, 
            use: p.T_UsingResolver, 
            shared:bool=None, 
            **opts) -> Callable[[T_Injectable], T_Injectable]:
        ...

    def resolver(self, tags: T_Injectable=..., use: p.T_UsingResolver =..., **kwds):
        def register(obj):
            if use is ...:
                tag, use_ = tags, obj
            else:
                tag, use_ = obj, use

            self.register(tag, use_, kind=KindOfProvider.resolver, **kwds)
            return obj
    
        if tags is ... or use is ...:
            return register
        else:
            return register(tags)    


