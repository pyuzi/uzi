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

    _requires: orderedset['IocContainer']
    _registry: dict[Injectable, Provider[T_UsingAny, T_Injected]]
    _bootstrapped: bool = False
    _pending: list[Provider]

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

        self._pending = []
        self.name = name
        self._bootstrapped = False
        self._init_registry()
        self._init_requires()
        self._init_dependants()
        self._requires.update(requires, self._default_requires)

    @property
    def bootstrapped(self):
        return self._bootstrapped

    def requires(self):
        return frozenorderedset(self._requires)

    @property
    @abstractmethod
    def _context(self) -> 'InjectorContext':
        ...

    @property
    def has_setup(self) -> bool:
        return self._context is not None

    def require(self, *containers: 'IocContainer') -> Self:
        self._requires |= containers
        return self

    def register_provider(self, provider: Provider) -> Self:
        if self._bootstrapped is not True:
            self._pending.append(provider)
            return self

        provider = provider.setup(self)
        if provider:
            inital = self._registry.setdefault(provider.provides, provider)
            if inital is not provider:
                raise DuplicateProviderError(f'{provider!r} and {inital=!r}')
        
        return self
    
    def bootstrap(self):
        if self._bootstrapped:
            raise RuntimeError(f'{self} already bootstrapped')
        
        print(f'{self}.bootstrap()')

        self._bootstrapped = True
        self._pop_pending()
        return self

    def _init_registry(self):
        self._registry = dict()

    def _init_requires(self):
        self._requires = orderedset()
     
    def _init_dependants(self):
        self.dependants = orderedset()
     
    def _pop_pending(self):
        while self._pending:
            self.register_provider(self._pending.pop())

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
   
    def __contains__(self, x):
        return x in self._registry

    def __getitem__(self, key: Injectable):
        try:
            return self._registry[key]
        except KeyError:
            return None




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
    
    # @cached_property
    # def repository(self):
    #     return self._create_repository()

    def is_provided(self, key) -> bool:
        return key in self
    
    def setup(self, ctx: 'InjectorContext') -> 'IocContainer':
        old = self._context
        if old is None:
            self._context = ctx
                
        elif ctx is not old:
            raise RuntimeError(
                f'InjectorContext conflict in {self}: {old=} -vs- new={ctx}'
            )
        self._bootstrapped or self.bootstrap()
        return self
        
    def teardown(self, ctx: 'InjectorContext') -> 'IocContainer':
        old = self._context
        if old is ctx:
            self._context = None

    # def _create_repository(self):
    #     return ChainMap({}, *(d.repository for d in self._requires))
    
    # def __contains__(self, x):
    #     if isinstance(x, IocContainer):
    #         return x is self \
    #             or x in self._requires \
    #             or any(x in d for d in self._requires)
    #     else:
    #         return x in self.repository
      
      
