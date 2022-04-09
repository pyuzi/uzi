from filecmp import cmp
import typing as t
from collections.abc import Iterable
from logging import getLogger

from typing_extensions import Self

import attr

from . import DependencyLocation, Injectable, InjectionMarker, is_injectable
from ._common import calling_frame
from ._common.collections import MultiChainMap, MultiDict
from .providers import Provider
from .providers.util import ProviderRegistry
from .scopes import Scope

logger = getLogger(__name__)



    
DEP_LOCAL = DependencyLocation.LOCAL
DEP_NONLOCAL = DependencyLocation.NONLOCAL
DEP_GLOBAL = DependencyLocation.GLOBAL

@InjectionMarker.register
@attr.s(slots=True, frozen=True, cmp=False, repr=False)
class Container(ProviderRegistry):

    name: str = attr.field(default='<anonymous>')
    parent: t.Union[Self, None] = attr.field(default=None)
    includes: tuple[Self] = attr.field(default=(), converter=tuple)
    inline: bool = attr.field(default=False, kw_only=True)

    _registries: dict[DependencyLocation, MultiChainMap[Injectable, Provider]] = attr.field(init=False)
    @_registries.default
    def _create_default_ns_map(self):
        return {
            DEP_LOCAL: (loc := MultiDict()),
            DEP_NONLOCAL: (nonloc := MultiChainMap()),
            DEP_GLOBAL: MultiChainMap(nonloc, loc),
        }

    def __attrs_post_init__(self):
        self._registries[DEP_NONLOCAL].maps[:] = (c.get_registry(DEP_GLOBAL) for c in self.includes)

    @property
    def __dependency__(self):
        return self

    def get_container(self, container: "Container" = None, *, only_self: bool=True):
        if (container or self) is self:
            return self
        elif container in self.includes:
            return container
        else:
            for con in self.includes:
                if con := con.get_container(container):
                    return con

    def include(self, *containers: "Container") -> Self:
        containers = (*(c for c in containers if c not in self.includes),)
        object.__setattr__(self, 'includes', self.includes + containers)
        self._registries[DEP_NONLOCAL].maps.extend(c.get_registry(DEP_GLOBAL) for c in containers)
        return self

    def register(self, provider: Provider) -> Self:
        provider.set_container(self)
        return self

    def add_to_registry(self, tag: Injectable, provider: Provider):
        self._registries[DEP_LOCAL][tag] = provider

    @t.overload
    def scope(self, parent: "Scope" = None) -> Scope:
        ...

    def scope(self, *a, **kw):
        return Scope(self, *a, **kw)

    def get_registry(self, loc: DependencyLocation = DEP_GLOBAL):
        return self._registries[loc]
      
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    def __contains__(self, x):
        if x in self._registries[DEP_GLOBAL]:
            return True
        elif isinstance(x, Container):
            return not not self.get_container(x)
        else:
            return not is_injectable(x) and NotImplemented or False
