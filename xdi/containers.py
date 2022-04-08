import typing as t
from collections.abc import Callable, Iterable
from logging import getLogger
from typing_extensions import Self

from xdi._common.collections import MultiChainMap, MultiDict, frozendict, orderedset
from xdi._common.functools import calling_frame, export
from xdi._common.promises import Promise

from . import Dependency, DependencyLocation, Injectable, T_Injected, InjectionMarker, is_injectable
from .providers import Provider, T_UsingAny
from .providers.util import ProviderRegistry
from .typing import get_origin
from .scopes import Scope


logger = getLogger(__name__)

_T = t.TypeVar("_T")




@InjectionMarker.register
class Container(ProviderRegistry):

    __slots__ = (
        "__name",
        "__bound",
        "__includes",
        "__boot",
        "__inline",
        "__autoloads",
        "_ns_local",
        "_ns_global",
        "_ns_nonlocal",
        "parent"
    )

    __boot: Promise

    __name: str
    __bound: orderedset["Scope"]
    __autoloads: orderedset[Injectable]

    __bound: orderedset["Scope"]
    __includes: orderedset["Container"]

    _ns_local: MultiDict[Injectable, Provider]
    _ns_nonlocal: MultiChainMap[Injectable, Provider]
    _ns_global: MultiChainMap[Injectable, Provider]

    parent: t.Union[Self, None]

    def __init__(
        self,
        name: str = None,
        include: Iterable["Container"] = (),
        *,
        parent: Self=None,
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

        self.__bound = orderedset()
        self.__autoloads = orderedset()
        self.__includes = orderedset()
        self.__boot = Promise()
        include and self.include(*include)

    @property
    def __dependency__(self):
        return self

    @property
    def autoloads(self):
        return (*self.__autoloads,)

    @property
    def locals(self):
        return self._ns_local

        
    @property
    def name(self) -> str:
        return self.__name

    def get_container(self, container: "Container"=None):
        if (container or self) is self:
            return self
        elif container in self.__includes:
            return container
        else:
            for con in self.__includes:
                if con := con.get_container(container):
                    return con
            
    def include(self, *containers: "Container", replace: bool = False) -> Self:
        if self._is_bound():
            raise TypeError(f"container already bound: {self!r}")
        elif replace:
            self.__includes = containers = orderedset(containers)
            self._ns_nonlocal.maps[:-1] = [c._ns_global for c in containers]
        else:
            self.__includes |= containers
            self._ns_nonlocal.maps[:-1] = [c._ns_global for c in self.__includes]
        return self

    def register(self, provider: Provider) -> Self:
        provider.set_container(self)
        return self

    def onboot(self, callback: t.Union[Promise, Callable, None] = None):
        self.__boot.then(callback)

    def add_to_registry(self, tag: Injectable, provider: Provider):
        self._ns_local[tag] = provider
        provider.autoloaded and self.__autoloads.add(tag)
        logger.debug(f'{self}.add_to_registry({tag}, {provider=!s})')

    @t.overload
    def scope(self, parent: 'Scope'=None) -> Scope : ...
    def scope(self, *a, **kw):
        return Scope(self, *a, **kw)

    def bind_scope(self, scope: "Scope"):
        if not self._is_bound(scope):
            logger.debug(f"{self}.bind({scope=})")
            self.__bound.add(scope)
            # scope.onboot(self.__boot)
            yield self, self._ns_local
            for c in reversed(self.__includes):
                yield from c.bind_scope(scope)

    def bind(self, injector: "Scope", source: "Container" = None):
        if not self._is_bound(injector):
            logger.debug(f"{self}.bind({injector=}, {source=})")
            self.__bound.add(injector)
            injector.onboot(self.__boot)
            yield self, self._ns_local
            yield from self._bind_included(injector)

    def _bind_included(self, injector: "Scope"):
        for c in reversed(self.__includes):
            yield from c.bind(injector, self)

    def _is_bound(self, injector: "Scope" = None):
        if injector is None:
            return not not self.__bound
        elif injector in self.__bound:
            return True
        elif not self.__inline:
            for b in self.__bound:
                if injector.has_scope(b):
                    return True
        return False

    def get_registry(self, loc: DependencyLocation=DependencyLocation.GLOBAL):
        if loc is DependencyLocation.GLOBAL:
            return self._ns_global
        elif loc is DependencyLocation.LOCAL:
            return self._ns_local
        elif loc is DependencyLocation.NONLOCAL:
            return self._ns_nonlocal
        raise ValueError(f'invalid argument {loc}')

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__name!r})"

    def __contains__(self, x):
        if x in self._ns_global:
            return True
        elif isinstance(x, Container):
            return not not self.get_container(x) 
        else:
            return not is_injectable(x) and NotImplemented or False
    