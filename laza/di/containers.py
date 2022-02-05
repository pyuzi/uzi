from abc import ABC, abstractmethod
from contextvars import ContextVar
from functools import update_wrapper
from logging import getLogger
import os
from types import FunctionType, GenericAlias, MappingProxyType
import typing as t

from collections import ChainMap
from collections.abc import Callable, Mapping, Sequence

from laza.common.typing import Self, get_origin
from laza.common.functools import export
from laza.common.collections import orderedset, fallbackdict, fallback_default_dict, frozenorderedset
from laza.common.saferef import SafeReferenceType, SafeRefSet, SafeKeyRefDict

from laza.common.functools import cached_property, calling_frame




from .common import (
    Injectable,
    InjectionToken,
    T_Injectable,
    T_Injected,
    unique_id
)
from .exc import DuplicateProviderError

from .providers import Provider, RegistrarMixin, T_UsingAny

if t.TYPE_CHECKING:
    from .injectors import Injector, InjectorContext


logger = getLogger(__name__)

_T = t.TypeVar('_T')





@export()
@Injectable.register
class AbcIocContainer(RegistrarMixin[T_Injected]):

    name: str
    dependants: orderedset['Injector']
    shared: bool = True
    _default_requires: t.ClassVar[orderedset['IocContainer']] = ()

    _registry: orderedset[Provider[T_UsingAny, T_Injected]]
    _requires: orderedset['IocContainer']
    _bindings: dict[Injectable, Provider[T_UsingAny, T_Injected]]
    _bootstrapped: bool = False
    _pending: orderedset[t.Any]

    def __init_subclass__(cls, **kwds) -> None:
        if '_default_requires' in cls.__dict__:
            cls._default_requires = orderedset(
                i or () for b in cls.__mro__ 
                    if issubclass(b, cls) 
                        for i in b._default_requires
            )
        return super().__init_subclass__(**kwds)

    def __init__(self, 
                *requires: 'IocContainer',
                name: str=None,
                shared: bool=None):

        if shared is not None:
            self.shared = shared

        self.name = name
        self._bootstrapped = False
        self._init_registry()
        self._init_requires()
        self._init_dependants()
        self._init_bindings()
        self._requires.update(requires, self._default_requires)

    @property
    def bootstrapped(self):
        return self._bootstrapped

    @property
    def bindings(self):
        return MappingProxyType(self._bindings)

    @property
    def registry(self):
        return frozenorderedset(self._registry)

    @property
    def requires(self):
        return frozenorderedset(self._requires)

    @property
    @abstractmethod
    def repository(self) -> Mapping[t.Any, Provider]:
        ...

    @property
    @abstractmethod
    def _context(self) -> 'InjectorContext':
        ...

    @property
    def has_setup(self) -> bool:
        return self._context is not None

    @cached_property
    def _resolvers(self):
        return self._create_resolvers()

    @cached_property
    def _linked_deps(self) -> dict[SafeReferenceType[T_Injectable], SafeRefSet[T_Injectable]]:
        return SafeKeyRefDict.using(lambda: fallback_default_dict(SafeRefSet))()

    def require(self, *containers: 'IocContainer') -> Self:
        self._requires |= containers
        return self

    def register_provider(self, provider: Provider) -> Self:
        return self.add(provider)

    def add(self, item: Provider) -> Self:
        if self._bootstrapped is not True:
            self._pending.add(item)
            return self
        
        binding = item.bind(self)
        if binding:
            inital = self._bindings.setdefault(binding.provides, binding)
            if inital is not binding:
                raise DuplicateProviderError(f'{binding!r} and {inital=!r}')
        
        return self
    
    def bootstrap(self):
        if self._bootstrapped:
            raise RuntimeError(f'{self} already bootstrapped')
        
        print(f'{self}.bootstrap()')

        self._bootstrapped = True
        self._empty_bind_stack()
        return self

    def _init_bindings(self):
        self._bindings = dict()
        self._pending = orderedset()

    def _init_registry(self):
        self._registry = orderedset()

    def _init_requires(self):
        self._requires = orderedset()
     
    def _init_dependants(self):
        self.dependants = orderedset()
     
    def _empty_bind_stack(self):
        stack = self._pending
        while stack:
            r = stack.pop().bind(self)
            print(f'  -{self}->{r._uses}, {r._provides}')

    def _create_resolvers(self):
       
        get_provider = self._bindings.get

        def fallback(key):
            if pro := get_provider(key):
                hand = pro.compile(key)
                return setdefault(key, self._register_handler(key, hand))
            elif origin := get_origin(key):
                if pro := get_provider(origin):
                    hand = pro.compile(key)
                    return setdefault(key, self._register_handler(key, hand))
            raise KeyError(key)

        res = fallbackdict(fallback)
        setdefault = res.setdefault
        return res

    def _register_handler(self, dep: Injectable, handler, deps: Sequence[Injectable]=None):
        if deps is None:
            deps = getattr(handler, 'deps', None) 

        if deps:
            graph = self._linked_deps
            for src in deps:
                graph[src].add(dep)
        return handler

    def add_dependant(self, scope: 'Injector'):
        self.dependants.add(scope)
        return self

    @abstractmethod
    def setup(self, ctx: 'InjectorContext') -> 'AbcIocContainer':
        ...
        
    @abstractmethod
    def teardown(self) -> t.NoReturn:
        ...

    def flush(self, tag, source=None):
        if source is None:
            for d in self.dependants:
                d.flush(tag, self)
   
  

    def __str__(self) -> str:
        return f'{self.__class__.__name__}({self.name!r})'

    def __repr__(self) -> str:
        requires = [*self._requires]
        return f'{self.__class__.__name__}({self.name!r}, {requires=!r})'
    
    # @property
    # @abstractmethod
    # def bindings(self):
    #     ...

    def __contains__(self, x):
        return x in self.repository
    
    # def __delitem__(self, key: Injectable):
    #     if not self.unprovide(key):
    #         raise KeyError(key)

    def __getitem__(self, key: Injectable):
        try:
            return self.repository[key]
        except KeyError:
            return None

    # def __setitem__(self, provide: Injectable, use: Provider):
    #     if not isinstance(use, Provider):
    #         raise TypeError(f'item must be a `Provider` and not `{type(use)}`')

    #     final = use.provide(provide).bind(self)   
    #     if final:
    #         original = self.registry.setdefault(final.provides, final)
    #         if original is not final:
    #             raise DuplicateProviderError(f'{provide!r} {final=!r}, {original=!r}')

    #     return  self.provide(provide, use)

    # def setdefault(self, key: Injectable, value: Provider=None):
    #     return self.provide(key, value, default=True)

    # def _setup_bindings(self) -> T_ProviderDict:
    #     if self.registry is not None:
    #         raise RuntimeError(f'bindings ready')
        
    #     self.registry = self._create_bindings_map()
        
    #     return dict()

    # def provide(self, 
    #         provide: t.Union[T_Injectable, None] , /,
    #         use: t.Union[Provider, T_UsingAny], 
    #         default: bool=None,
    #         **kwds):

    #     provider = self.create_provider(provide, use, **kwds)

    #     if provide is None:
    #         provide = provider._uses_fallback()
    #         if provide is NotImplemented:
    #             raise ValueError(f'no implicit tag for {provider!r}')

    #     if not isinstance(provide, Injectable):
    #         raise TypeError(f'injector tag must be Injectable not {provide.__class__.__name__}: {provide}')

    #     original = self.registry.setdefault(provide, provider)
    #     if original is not provider:
    #         if default is True:
    #             return original
    #         raise DuplicateProviderError(f'{provide!r} {provider=!r}, {original=!r}')
    #     self.flush(provide)
    #     return provider
        
    # def create_provider(self, provide, use: t.Union[Provider, T_UsingAny], **kwds: dict) -> Provider:
    #     if isinstance(use, Provider):
    #         if kwds:
    #             raise ValueError(f'got unexpected keyword arguments {tuple(kwds)}')
    #         return use

    #     cls = self._get_provider_class(provide, use, kwds)
    #     return cls(use, **kwds)

    # def _get_provider_class(self, provide, use, kwds: dict) -> type[Provider]:
    #     raise LookupError(f'unkown provider: {provide=} {use=}')




@export()
class IocContainer(AbcIocContainer):

    shared: bool = True
    _context: 'InjectorContext' = None

    def __init__(self, 
                *requires: 'IocContainer',
                name: str=None,
                shared: bool=None):

        if not name:
            name = calling_frame(1, globals=True)['__package__']
            name = f'{name}[{unique_id(name)}]'
            
        super().__init__(*requires, name=name, shared=shared)
    
    # @property
    # def _context(self): # -> 'InjectorContext':
    #     if dep := next(iter(self.dependants), None):
    #         return dep._context

    @cached_property
    def repository(self):
        return self._create_repository()

    def is_provided(self, key) -> bool:
        return key in self
    
    def setup(self, ctx: 'InjectorContext') -> 'IocContainer':
        self._bootstrapped or self.bootstrap()
        old = self._context
        if old is None:
            self._context = ctx
                
        elif ctx is not old:
            raise RuntimeError(
                f'InjectorContext conflict in {self}: {old=} -vs- new={ctx}'
            )
        return self
        
    def teardown(self, ctx: 'InjectorContext') -> 'IocContainer':
        old = self._context
        if old is ctx:
            self._context = None

    def _setup_bindings(self):
        loc = self._bindings
        for x in self._registry:
            b = x.bind(self)
            loc[b.pro] = b

    def _create_repository(self):
        return ChainMap({}, *(d.repository for d in self._requires))
    
    def __contains__(self, x):
        if isinstance(x, IocContainer):
            return x is self \
                or x in self._requires \
                or any(x in d for d in self._requires)
        else:
            return x in self.repository
      
    # def add_dependant(self, scope: 'AbcScope'):
    #     super().add_dependant(scope)
    #     if self._context is None:
    #         self._context = scope._context
        
    #     return self

