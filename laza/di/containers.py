from abc import ABC, ABCMeta, abstractmethod
from contextvars import ContextVar
from functools import update_wrapper
from logging import getLogger
import os
from threading import Lock
from time import monotonic_ns
import typing as t

from collections.abc import Iterable, Callable

from laza.common.typing import Self
from laza.common.functools import export
from laza.common.collections import orderedset, multidict


from laza.common.functools import calling_frame

from libs.di.laza.di.functools import Bootable




from .common import (
    Injectable,
    T_Injected,
)

from .providers import Provider, RegistrarMixin, T_UsingAny


if t.TYPE_CHECKING:
    from .injectors import Injector, InjectorContext


logger = getLogger(__name__)

_T = t.TypeVar('_T')



@export()
@Injectable.register
class IocContainer(Bootable, RegistrarMixin[T_Injected]):

    
    name: str
    _bound: orderedset['Injector']
    is_singleton: bool = True
    _default_requires: t.ClassVar[orderedset['IocContainer']] = ()

    _bound: orderedset['Injector']
    _requires: orderedset['IocContainer']
    _registry: dict[Injectable, Provider[T_UsingAny, T_Injected]]
    # is_bootstrapped: bool = False

    _context = None

    def __init__(self, 
                name: str=None,
                requires: Iterable['IocContainer'] = (),
                singleton: bool=None):
        super().__init__()
        
        if not name:
            fr = calling_frame(chain=True)
            name = name = fr.get('__name__') or fr.get('__package__') or '<anonymous>'
         
        self.is_singleton = not singleton is False
        self.name = name
        
        self._bound = orderedset()
        self._registry = multidict()
        self._requires = orderedset()
        requires and self.require(*requires)

    def require(self, *containers: 'IocContainer', replace: bool=False) -> Self:
        if replace:
            self._requires = orderedset(containers)    
        else:
            self._requires |= containers
        return self

    def register_provider(self, provider: Provider) -> Self:
        if self.is_booted:
            provider.set_container(self)
        else:
            self.on_boot(lambda s: provider.set_container(s))    
        return self

    def add_to_registry(self, tag: Injectable, provider: Provider):
        self.flush(tag)
        self._registry[tag] = provider
        logger.debug(f'{self}.add_to_registry({tag}, {provider=!s})')

    def bind(self, injector: 'Injector', source: 'IocContainer'=None):
        if not self.is_bound(injector):

            self.boot()

            self._bound.add(injector)

            logger.debug(f'{self}.bound({injector=}, {source=})')

            return self._ibind(injector)

    def _ibind(self, injector: 'Injector'):
        yield self
        yield from self._bind_required(injector)

    def _bind_required(self, injector: 'Injector'):
        for c in reversed(self._requires):
            yield from c.bind(injector, self)

    def is_bound(self, inj: 'Injector'=None):
        if inj is None:
            return not not self._bound
        elif inj in self._bound:
            return True
        elif self.is_singleton:
            for b in self._bound:
                if inj in {*b.parents()}:
                    return True
        return False

    def flush(self, tag, source=None):
        if source is None:
            bound = self._bound
            for inj in bound:
                if not any(p in bound for p in inj.parents()):
                    inj.flush(tag, self)
   
    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.name!r}, #{self.bootid})'
   
    # def __contains__(self, x):
    #     return x in self._registry

    def __getitem__(self, key: Injectable):
        try:
            return self._registry[key]
        except KeyError:
            return None





@export()
class InjectorContainer(IocContainer):
    
    _injector: 'Injector'

    def __init__(self, injector: 'Injector'):
        super().__init__(injector.name, singleton=True)
        self._injector = injector
    
    def bind(self, injector: 'Injector'=None, source: 'IocContainer'=None):
        if injector is None:
            injector = self._injector

        if not source is None:
            raise TypeError(f'{self} cannot be required in other containers.')
        elif not self._injector is injector:
            raise TypeError(f'{self} already belongs to {self._injector}')
        return super().bind(injector)
     
    # def _ibind(self, injector: 'Injector'):
    #     yield from self._bind_required(injector)
    #     yield self
