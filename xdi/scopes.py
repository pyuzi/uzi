from collections import defaultdict
from copy import copy
import typing as t 
from collections.abc import Mapping

from typing_extensions import Self

import attr



from . import DependencyLocation, InjectionMarker, Injectable, Dependency
from .providers.util import BindingsMap
from .providers import Provider
from .typing import get_origin
from .injectors import Injector, NullInjectorContext



if t.TYPE_CHECKING:
    from .containers import Container


def dict_copy(obj):
    return copy(obj) if isinstance(obj, Mapping) else dict(obj or ())


@attr.s(slots=True, frozen=True, cmp=False)
class Scope:

    container: 'Container' =  attr.field()
    parent: Self = attr.field(factory=lambda: NullScope())
    _dependencies: dict = attr.field(factory=dict, converter=dict_copy, eq=False, repr=False)
    _injector_class: type[Injector] = attr.field(default=Injector, repr=False)
    _resolved: defaultdict[Injectable, dict[tuple, Dependency]] = attr.field(factory=lambda: defaultdict(dict), init=False, repr=False)

    @_injector_class.validator
    def _check_injector_class(self, attrib, val):
        if not issubclass(val, Injector):
            raise TypeError(
                f"'injector_class' must be a subclass of "
                f"{Injector.__qualname__!r}. "
                f"Got {val.__class__.__qualname__}."
            )

    @property
    def name(self) -> str:
        return self.container.name

    def __contains__(self, key):
        return key in self._resolved \
            or key in self.container \
            or key in self._dependencies
   
    def is_provided(self, key, *, only_self: bool=False):
        return isinstance(key, Provider) or key in self or (not only_self and self.parent.is_provided(key))
   
    def __getitem__(self, key):
        try:
            return self._dependencies[key]
        except KeyError:
            return self.__missing__(key)
        except TypeError:
            if key.__class__ is slice:
                return self[key.start] or self.parent[key]
            raise
        
    def __missing__(self, key):
        if key.__class__ is Dependency:
            return self._dependencies.setdefault(key, key(self))
        elif dep := self.resolve_dependency(key):
            return self[dep]
        elif self.is_provided(key):
            return self._dependencies.setdefault(key)

    def resolve_dependency(self, key: Injectable, container: 'Container'=None, loc: DependencyLocation=DependencyLocation.GLOBAL, *, only_self: bool=False):
        if container := self.container.get_container(container):
            ident = container, loc
            resolved = self._resolved[key]
            if ident in resolved:
                return resolved[ident]
            
            if isinstance(key, Provider):
                pros = [key]
            else:
                ns = container.get_registry(loc)
                pros = ns.get_all(key)
                if not pros and (origin := get_origin(key)):
                    pros = ns.get_all(origin)
            if pros:
                if pro := pros[0].compose(self, key, *pros[1:]):
                    resolved[ident] = dp = Dependency(key, self, pro)
                    return dp
            
            if not (container is self.container or loc is DependencyLocation.LOCAL):
                if dp := self.resolve_dependency(key, None, loc, only_self=True):
                    resolved[ident] = dp
                    return dp
            
            if not container.parent and loc is DependencyLocation.LOCAL:
                return 
            container = container.parent

        if not only_self:        
            return self.parent.resolve_dependency(key, container, loc)

    def injector(self, parent: t.Union[Injector, None]=NullInjectorContext()):
        if self.parent and not (parent and self.parent in parent):
            parent = self.parent.injector(parent)
        elif parent and self in parent:
            raise TypeError(f'Injector {parent} in scope.')
        
        return self.create_injector(parent)
        
    def create_injector(self, parent: Injector=NullInjectorContext()):
        return self._injector_class(parent, self)

    def __eq__(self, o) -> bool:
        return o is self # isinstance(o, Scope) and o.container == self.container

    def __hash__(self):
        return id(self)



class NullScope:
    
    __slots__ = ()

    def __init__(self): ...

    def __bool__(self): return False

    def __contains__(self, key): return False

    def is_provided(self, key, **kw): return False

    def __getitem__(self, key):
        return None

    def __repr__(self): return f'{self.__class__.__qualname__}()'

    def resolve_dependency(self, *a, **kw): return