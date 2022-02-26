from logging import getLogger
import typing as t

from collections.abc import Iterable, Callable

from laza.common.typing import Self
from laza.common.functools import export
from laza.common.collections import orderedset, multidict


from laza.common.functools import calling_frame

from laza.common.promises import Promise




from .common import (
    Injectable,
    T_Injected,
)

from .providers import Provider, T_UsingAny
from .providers.util import ProviderRegistry



if t.TYPE_CHECKING:
    from .injectors import Injector


logger = getLogger(__name__)

_T = t.TypeVar('_T')



@export()
@Injectable.register
class Container(ProviderRegistry):

    __slots__ = (
        '__name', '__bound', '__includes', '__registry', '__boot', '__inline',
        '__autoloads'
    )
    
    __boot: Promise

    __name: str
    __bound: orderedset['Injector']
    __autoloads: orderedset[Injectable]

    __bound: orderedset['Injector']
    __includes: orderedset['Container']
    __registry: dict[Injectable, Provider[T_UsingAny, T_Injected]]

    def __init__(self, 
                name: str=None,
                include: Iterable['Container'] = (), 
                *, 
                inline: bool =False):
        
        if not name:
            fr = calling_frame(chain=True)
            name = name = fr.get('__name__') or fr.get('__package__') or '<anonymous>'
         
        self.__name = name
        self.__inline = inline
        
        self.__bound = orderedset()
        self.__autoloads = orderedset()
        self.__registry = multidict()
        self.__includes = orderedset()
        self.__boot = Promise()
        include and self.include(*include)

    @property
    def autoloads(self):
        return *self.__autoloads,

    @property
    def name(self) -> str:
        return self.__name

    def include(self, *containers: 'Container', replace: bool=False) -> Self:
        if self._is_bound():
            raise TypeError(f'container already bound: {self!r}')
        elif replace:
            self.__includes = orderedset(containers)    
        else:
            self.__includes |= containers
        return self

    def register(self, provider: Provider) -> Self:
        self.onboot(lambda: provider.set_container(self))
        return self

    def onboot(self, callback: t.Union[Promise, Callable, None]=None):
        self.__boot.then(callback)

    def add_to_registry(self, tag: Injectable, provider: Provider):
        if not self.__boot.done():
            raise TypeError(f'container not booted: {self!r}')
        self.__registry[tag] = provider
        provider.autoloaded and self.__autoloads.add(tag)
        # logger.debug(f'{self}.add_to_registry({tag}, {provider=!s})')

    def bind(self, injector: 'Injector', source: 'Container'=None):
        if not self._is_bound(injector):
            logger.debug(f'{self}.bind({injector=}, {source=})')
            self.__bound.add(injector)
            yield self, self.__registry
            yield from self._bind_included(injector)
            injector.onboot(self.__boot)

    def _bind_included(self, injector: 'Injector'):
        for c in reversed(self.__includes):
            yield from c.bind(injector, self)

    def _is_bound(self, injector: 'Injector'=None):
        if injector is None:
            return not not self.__bound
        elif injector in self.__bound:
            return True
        elif not self.__inline:
            for b in self.__bound:
                if injector.has_scope(b):
                    return True
        return False
   
    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.__name!r}, {self.__bound})'
  



@export()
class InjectorContainer(Container):
    
    __slots__ = '__injector',

    __injector: 'Injector'

    def __init__(self, injector: 'Injector'):
        super().__init__(injector.name)
        self.__injector = injector
    
    def bind(self, injector: 'Injector'=None, source: 'Container'=None):
        if injector is None:
            injector = self.__injector

        if not source is None:
            raise TypeError(f'{self} cannot be required in other containers.')
        elif not self.__injector is injector:
            raise TypeError(f'{self} already belongs to {self.__injector}')
        return super().bind(injector)
     

