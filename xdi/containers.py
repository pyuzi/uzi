import typing as t
from collections.abc import Iterable
from logging import getLogger

from typing_extensions import Self

from . import DependencyLocation, Injectable, InjectionMarker, is_injectable
from ._common import calling_frame
from ._common.collections import MultiChainMap, MultiDict
from .providers import Provider
from .providers.util import ProviderRegistry
from .scopes import Scope

logger = getLogger(__name__)


@InjectionMarker.register
class Container(ProviderRegistry):

    __slots__ = (
        "__name",
        "__includes",
        "__inline",
        "_ns_local",
        "_ns_global",
        "_ns_nonlocal",
        "parent",
    )

    __name: str

    __includes: tuple[Self]

    _ns_local: MultiDict[Injectable, Provider]
    _ns_nonlocal: MultiChainMap[Injectable, Provider]
    _ns_global: MultiChainMap[Injectable, Provider]

    parent: t.Union[Self, None]

    def __init__(
        self,
        name: str = None,
        include: Iterable["Container"] = (),
        *,
        parent: Self = None,
        inline: bool = False,
    ):

        if not name:
            fr = calling_frame(chain=True)
            name = name = fr.get("__name__") or fr.get("__package__") or "<anonymous>"

        self.__name = name
        self.__inline = inline
        self.parent = parent
        self._ns_local = MultiDict()
        self._ns_nonlocal = MultiChainMap()
        self._ns_global = MultiChainMap(self._ns_nonlocal, self._ns_local)

        self.__includes = ()
        include and self.include(*include)

    @property
    def __dependency__(self):
        return self

    @property
    def locals(self):
        return self._ns_local

    @property
    def name(self) -> str:
        return self.__name

    def get_container(self, container: "Container" = None):
        if (container or self) is self:
            return self
        elif container in self.__includes:
            return container
        else:
            for con in self.__includes:
                if con := con.get_container(container):
                    return con

    def include(self, *containers: "Container") -> Self:
        containers = (*(c for c in containers if c not in self.__includes),)
        self.__includes = self.__includes + containers
        self._ns_nonlocal.maps.extend(c._ns_global for c in containers)
        return self

    def register(self, provider: Provider) -> Self:
        provider.set_container(self)
        return self

    def add_to_registry(self, tag: Injectable, provider: Provider):
        self._ns_local[tag] = provider
        # provider.autoloaded and self.__autoloads.add(tag)
        logger.debug(f"{self}.add_to_registry({tag}, {provider=!s})")

    @t.overload
    def scope(self, parent: "Scope" = None) -> Scope:
        ...

    def scope(self, *a, **kw):
        return Scope(self, *a, **kw)

    # def bind_scope(self, scope: "Scope"):
    #     if not self._is_bound(scope):
    #         logger.debug(f"{self}.bind({scope=})")
    #         self.__bound.add(scope)
    #         yield self, self._ns_local
    #         for c in reversed(self.__includes):
    #             yield from c.bind_scope(scope)

    # def _is_bound(self, injector: "Scope" = None):
    #     if injector is None:
    #         return not not self.__bound
    #     elif injector in self.__bound:
    #         return True
    #     elif not self.__inline:
    #         for b in self.__bound:
    #             if injector.has_scope(b):
    #                 return True
    #     return False

    def get_registry(self, loc: DependencyLocation = DependencyLocation.GLOBAL):
        if loc is DependencyLocation.GLOBAL:
            return self._ns_global
        elif loc is DependencyLocation.LOCAL:
            return self._ns_local
        elif loc is DependencyLocation.NONLOCAL:
            return self._ns_nonlocal
        raise ValueError(f"invalid argument {loc}")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__name!r})"

    def __contains__(self, x):
        if x in self._ns_global:
            return True
        elif isinstance(x, Container):
            return not not self.get_container(x)
        else:
            return not is_injectable(x) and NotImplemented or False
