from logging import getLogger
import typing as t

import attr
from typing_extensions import Self
from collections.abc import Set
from numpy import source

from xdi._common import private_setattr
from xdi._common import frozendict

from . import Injectable
from .injectors import Injector, NullInjectorContext
from ._dependency import Dependency

from .containers import Container
from xdi import containers


logger = getLogger(__name__)

class EmptyScopeError(RuntimeError):
    ...



@attr.s(slots=True, frozen=True, cmp=False)
@private_setattr
class Scope(frozendict[tuple, t.Union[Dependency, None]]):

    container: 'Container' = attr.ib(repr=True)
    parent: Self = attr.ib(factory=lambda: NullScope())
   
    path: tuple = attr.ib(init=False, repr=True)
    @path.default
    def _init_path(self):
        return  self.container, *self.parent.path,

    _v_hash: int = attr.ib(init=False, repr=False)
    @_v_hash.default
    def _init_v_hash(self):
        return hash(self.path)

    _injector_class: type[Injector] = attr.ib(kw_only=True, default=Injector, repr=False)
    
    maps: Set[Container] = attr.ib(init=False, repr=True)
    @maps.default
    def _init_maps(self):
        container, parent = self.container, self.parent
        if dct := {c:c for c in container._dro_entries_() if not c in parent}:
            return t.cast(Set[Container], dct.keys())
        raise EmptyScopeError(f'{container=}, {parent=}')

    __contains = dict.__contains__
    __setdefault = dict.setdefault

    @property
    def name(self) -> str:
        return self.container.name

    @property
    def level(self) -> int:
        return self.parent.level + 1

    def parents(self):
        parent = self.parent
        while parent:
            yield parent
            parent = parent.parent
 
    def resolve_provider(self, abstract: Injectable, source: Container=None):
        rv = None
        for container in self.maps:
            if pro := container[abstract]:
                if not pro.is_default:
                    return pro
                elif not rv:
                    rv = pro
        return rv
        
    # def injector(self, parent: t.Union[Injector, None] = NullInjectorContext()):
    #     if self.parent and not (parent and self.parent in parent):
    #         parent = self.parent.injector(parent)
    #     elif parent and self in parent:
    #         raise TypeError(f"Injector {parent} in scope.")

    #     return self.create_injector(parent)

    # def create_injector(self, parent: Injector = NullInjectorContext()):
    #     return self._injector_class(parent, self)

    def __bool__(self):
        return True
    
    def __contains__(self, o) -> bool:
        return self.__contains(o) or o in self.maps or o in self.parent

    def __missing__(self, abstract: Injectable) -> t.Union[Dependency, None]:
        if pro := self.resolve_provider(abstract):
            return self.__setdefault(abstract, pro.compose(self, abstract) or self.parent[abstract])
        elif dep := self.parent[abstract]:
            return self.__setdefault(abstract, dep)
            
    def __eq__(self, o) -> bool:
        if isinstance(o, Scope):
            return o.path == self.path 
        return NotImplemented

    def __ne__(self, o) -> bool:
        if isinstance(o, Scope):
            return o.path != self.path 
        return not self == o

    def __hash__(self):
        return self._v_hash





class NullScope(Scope):
    __slots__ = ()
    parent = None
    container = frozendict()
    maps = frozenset()
    level = -1
    path = ()
    _v_hash = hash(path)

    def __init__(self) -> None: ...

    def __bool__(self): 
        return False
    def __repr__(self): 
        return f'{self.__class__.__name__}()'
    def __contains__(self, key): 
        return False
    def __getitem__(self, key): 
        return None
        