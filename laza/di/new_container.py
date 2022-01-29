from logging import getLogger
import os
from types import GenericAlias
import typing as t

from collections import ChainMap
from collections.abc import Callable, Mapping, Sequence

from laza.common.functools import export
from laza.common.collections import orderedset

from laza.common.functools import cached_property, calling_frame



from . import providers as p
from .injectors import Injector
from .common import (
    Injectable,
    T_Injectable,
    unique_id
)

from .registries import ProviderRegistry

if t.TYPE_CHECKING:
    from .new_scopes import Scope


logger = getLogger(__name__)




@export()
@Injectable.register
class BaseContainer(ProviderRegistry):

    name: str
    requires: orderedset['Container']
    dependants: orderedset['Container']
    shared: bool = True

    def __init__(self, 
                *requires: 'Container',
                name: str=None,
                shared: bool=None):

        if shared is not None:
            self.shared = shared

        self.name = name
        self._setup_requires()
        self._setup_dependants()
        requires and self.requires.update(requires)
        # self[self] = p.InjectorProvider()

    def __str__(self) -> str:
        return f'{self.__class__.__name__}({self.name!r})'

    def __repr__(self) -> str:
        requires = [*self.requires]
        return f'{self.__class__.__name__}({self.name!r}, {requires=!r})'

    def _setup_requires(self):
        self.requires = orderedset()
     
    def _setup_dependants(self):
        self.dependants = orderedset()
     
    def add_dependant(self, scope: 'Scope'):
        self.dependants.add(scope)
        return self

    def flush(self, tag, source=None):
        if source is None:
            for d in self.dependants:
                d.flush(tag, self)
        
    


@export()
class Container(BaseContainer):

    shared: bool = True

    def __init__(self, 
                *requires: 'Container',
                name: str=None,
                shared: bool=None):

        if not name:
            name = calling_frame(1, globals=True)['__package__']
            name = f'{name}[{unique_id(name)}]'
            
        super().__init__(*requires, name=name, shared=shared)
    
    @cached_property
    def repository(self):
        return self._create_repository()
    
    def _create_repository(self):
        return ChainMap({}, *(d.repository for d in self.requires))
 
    def __contains__(self, x):
        if isinstance(x, Container):
            return x is self \
                or x in self.requires \
                or any(x in d for d in self.requires)
        else:
            return super().__contains__(x)
    