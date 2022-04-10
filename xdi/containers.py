from enum import IntEnum, auto
from filecmp import cmp
import typing as t
from collections.abc import Iterable
from logging import getLogger

from typing_extensions import Self

import attr

from . import Injectable, InjectionMarker, is_injectable
from ._common import calling_frame
from ._common.collections import MultiChainMap, MultiDict
from .providers import Provider
from .providers.util import ProviderRegistry

logger = getLogger(__name__)



class ContainerContext(IntEnum):

    GLOBAL: "ContainerContext" = 0
    """start resolving from the current/given scope and it's parent.
    """

    NONLOCAL: "ContainerContext" = auto()
    """Skip the current/given container and resolve from it's peers or parent instead.
    """

    LOCAL: "ContainerContext" = auto()
    """Only inject from the current/given container without considering it's peers and parent
    """

    # @classmethod
    # def coerce(cls, val):
    #     return cls(val or 0)

    
CTX_LOCAL = ContainerContext.LOCAL
CTX_NONLOCAL = ContainerContext.NONLOCAL
CTX_GLOBAL = ContainerContext.GLOBAL



@attr.s(slots=True, frozen=True, repr=False)
class IocGraph:

    container: 'Container' = attr.field()
    root: Self = attr.field(default=None)

    nodes: dict['Container', Self] = attr.field(init=False)
    @nodes.default
    def _default_nodes(self):
        return {
            c: self.__class__(c, self)
            for c in self.container.includes
        }


    def __getitem__(self, key):
        pass
        




@InjectionMarker.register
@attr.s(slots=True, frozen=True, cmp=False, repr=False)
class Container(ProviderRegistry):

    name: str = attr.field(default='<anonymous>')
    parent: t.Union[Self, None] = attr.field(default=None)
    includes: tuple[Self] = attr.field(default=(), converter=tuple)
    inline: bool = attr.field(default=False, kw_only=True)

    _registries: dict[ContainerContext, MultiChainMap[Injectable, Provider]] = attr.field(init=False)
    @_registries.default
    def _create_default_ns_map(self):
        return {
            CTX_LOCAL: (loc := MultiDict()),
            CTX_NONLOCAL: (nonloc := MultiChainMap()),
            CTX_GLOBAL: MultiChainMap(nonloc, loc),
        }

    def __init_subclass__(cls, *args, **kwargs):
        if not hasattr(cls, fn := f'_{cls.__name__}__set_attr'):
            setattr(cls, fn, Container.__set_attr)

    def __set_attr(self, name=None, value=None, /, **kw):
        name and kw.setdefault(name. value)
        for k,v in kw.items():
            object.__setattr__(self, k, v)

    def __attrs_post_init__(self):
        self._registries[CTX_NONLOCAL].maps[:] = (c.get_registry(CTX_GLOBAL) for c in self.includes)

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
        self._registries[CTX_NONLOCAL].maps.extend(c.get_registry(CTX_GLOBAL) for c in containers)
        return self

    def register(self, provider: Provider) -> Self:
        provider.set_container(self)
        return self

    def add_to_registry(self, tag: Injectable, provider: Provider):
        self._registries[CTX_LOCAL][tag] = provider

    @t.overload
    def scope(self, parent: "Scope" = None) -> "Scope":
        ...

    def scope(self, *a, **kw):
        return Scope(self, *a, **kw)

    def get_registry(self, loc: ContainerContext = CTX_GLOBAL):
        return self._registries[loc]
      
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    def __contains__(self, x):
        if x in self._registries[CTX_GLOBAL]:
            return True
        elif isinstance(x, Container):
            return not not self.get_container(x)
        else:
            return not is_injectable(x) and NotImplemented or False



from .scopes import Scope
