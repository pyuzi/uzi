from copy import copy
import typing as t 
from collections.abc import Mapping

from typing_extensions import Self

import attr

from xdi._common.collections import MultiChainMap, emptydict, frozendict, frozenorderedset, MultiDict


from . import InjectionMarker, Injectable, Dependency
from .providers.util import BindingsMap
from .providers import Provider
from .typing import get_origin
from .injectors import Injector, NullInjectorContext



if t.TYPE_CHECKING:
    from .containers import Container


def dict_copy(obj):
    return copy(obj) if isinstance(obj, Mapping) else dict(obj or ())


@attr.s(slots=False)
class Scope:

    container: 'Container' =  attr.field()
    parent: Self = attr.field(factory=lambda: NullScope())
    _resolver_map: BindingsMap = attr.field(factory=dict, converter=dict_copy, eq=False, repr=True)
    _injector_class: type[Injector] = attr.field(default=Injector, repr=False)

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
        return key in self._resolver_map\
            or key in self.container \
            or (not isinstance(key, Dependency) and Dependency(key, self) in self._resolver_map)
   
    def is_provided(self, key, *, only_self: bool=False):
        return key in self or (not only_self and self.parent.is_provided(key))
   
    def __getitem__(self, key):
        try:
            return self._resolver_map[key]
        except KeyError:
            return self.__missing__(key)
        except TypeError:
            if key.__class__ is slice:
                return self[key.start] or self.parent[key]
            raise
    
    def __missing__(self, key):
        container = self.container
        
        if isinstance(key, Dependency):
            dep, pros = key.dependency, container[key]
        elif isinstance(key, Provider):
            dep, pros = key, [key],
        else:
            # dep, pros = key, container[key]
            return self[Dependency(key, self)]

        store = self._resolver_map
        if pros:
            pro = pros[0].compose(self, dep, *pros[1:])
            return store.setdefault(key, pro and pro.bind(self, dep))
        elif isinstance(dep, InjectionMarker) and dep != dep.__dependency__:
            return store.setdefault(key, self[dep.__dependency__])
        elif key in self.parent:
            return store.setdefault(key, None)
        
    def injector(self, parent: t.Union[Injector, None]=NullInjectorContext()):
        if self.parent and not (parent and self.parent in parent):
            parent = self.parent.injector(parent)
        elif parent and self in parent:
            raise TypeError(f'Injector {parent} in scope.')
        
        return self.create_injector(parent)
        
    def create_injector(self, parent: Injector=NullInjectorContext()):
        return self._injector_class(parent, self)






class NullScope:
    
    __slots__ = ()

    def __init__(self): ...

    def __bool__(self): return False

    def __contains__(self, key): return False

    def is_provided(self, key, **kw): return False

    def __getitem__(self, key):
        return None