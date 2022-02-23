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

from laza.common.promises import Promise

from laza.common.functools import uniqueid



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
class BaseContainer(RegistrarMixin[T_Injected]):

    __slots__ = (
        'name', '_bound', '_requires', '_registry', '_onboot',
    )
    
    _onboot: Promise

    name: str
    _bound: orderedset['Injector']
    _is_inline: t.ClassVar[bool] = False

    _bound: orderedset['Injector']
    _requires: orderedset['BaseContainer']
    _registry: dict[Injectable, Provider[T_UsingAny, T_Injected]]

    def __init__(self, 
                name: str=None,
                requires: Iterable['BaseContainer'] = ()):
        
        if not name:
            fr = calling_frame(chain=True)
            name = name = fr.get('__name__') or fr.get('__package__') or '<anonymous>'
         
        self.name = name
        
        self._bound = orderedset()
        self._registry = multidict()
        self._requires = orderedset()
        self._onboot = Promise()
        requires and self.require(*requires)

    def boot(self) -> Self:
        if self._onboot.is_pending and self._can_boot():
            logger.debug(f'BOOTING:{self} => {self._onboot}')
            self._do_boot() 
            logger.debug(f'BOOTED:{self}  => {self._onboot}')
        return self

    def _do_boot(self):
        self._onboot.fulfil(uniqueid[Container])

    def _can_boot(self) -> bool:
        return self.is_bound()
         
    def require(self, *containers: 'BaseContainer', replace: bool=False) -> Self:
        if replace:
            self._requires = orderedset(containers)    
        else:
            self._requires |= containers
        return self

    def register_provider(self, provider: Provider) -> Self:
        self._onboot.then(lambda v: provider.set_container(self))
        return self

    def add_to_registry(self, tag: Injectable, provider: Provider):
        self._registry[tag] = provider
        logger.debug(f'{self}.add_to_registry({tag}, {provider=!s})')

    def bind(self, injector: 'Injector', source: 'BaseContainer'=None):
        logger.debug(f'{self}.is_bound({injector})')

        if not self.is_bound(injector):
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
        logger.debug(f'{self}.is_bound({inj})')
        if inj is None:
            return not not self._bound
        elif inj in self._bound:
            return True
        elif not self._is_inline:
            for b in self._bound:
                if inj in {*b.parents()}:
                    return True
        return False

    # def flush(self, tag, source=None):
    #     if source is None:
    #         bound = self._bound
    #         for inj in bound:
    #             if not any(p in bound for p in inj.parents()):
    #                 inj.flush(tag, self)
   
    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.name!r}, #{self._onboot})'
  
    # def __getitem__(self, key: Injectable):
    #     try:
    #         return self._registry[key]
    #     except KeyError:
    #         return None





@export()
class Container(BaseContainer):

    __slots__ = ()
    _is_inline: t.Final = False



@export()
class InjectorContainer(Container):
    
    __slots__ = '_injector',

    _injector: 'Injector'

    def __init__(self, injector: 'Injector'):
        super().__init__(injector.name)
        self._injector = injector
    
    def bind(self, injector: 'Injector'=None, source: 'BaseContainer'=None):
        if injector is None:
            injector = self._injector

        if not source is None:
            raise TypeError(f'{self} cannot be required in other containers.')
        elif not self._injector is injector:
            raise TypeError(f'{self} already belongs to {self._injector}')
        return super().bind(injector)
     



@export()
class InlineContainer(BaseContainer):
    
    __slots__ = ()

    _is_inline: t.Final = True
