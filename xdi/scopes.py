from enum import Flag, auto
from functools import lru_cache, reduce
from operator import or_
import typing as t

import attr
import networkx as nx
from typing_extensions import Self

from xdi._common import private_setattr
from xdi._common.collections import frozendict

from . import Injectable
from .injectors import Injector, NullInjectorContext
from ._dependency import Dependency

from .containers import Container


class ResolutionStrategy(Flag):

    INNER:  'ResolutionStrategy' = auto()
    OUTER:  'ResolutionStrategy' = auto()
    UPPER:  'ResolutionStrategy' = auto()

    @lru_cache(128)
    def _members(self):
        return dict.fromkeys(m for m in self.__class__ if m in self).keys()

    def __iter__(self):
        yield from self._members()





@attr.s(slots=True, frozen=True, cmp=True, cache_hash=True)
class DepKey:
    abstract: Injectable = attr.ib()
    container: Container = attr.ib(default=None)
    strategy: ResolutionStrategy = attr.ib(default=reduce(or_, ResolutionStrategy))
    # maxdepth: int = attr.ib(default=None)

    def __iter__(self):
        yield self.abstract
        yield self.container
        yield self.strategy



@attr.s(slots=True, frozen=True, cmp=False)
@private_setattr
class Scope(frozendict[tuple, t.Union[Dependency, None]]):

    container: 'Container' = attr.ib(repr=True)
    parent: Self = attr.ib(factory=lambda: NullRootScope())
    @parent.validator
    def _check_parent(self, attrib, val):
        assert isinstance(val, Scope)

    path: tuple = attr.ib(init=False, repr=True)
    @path.default
    def _init_path(self):
        return  self.container, *self.parent.path,

    strategy: ResolutionStrategy = attr.ib(kw_only=True, default=ResolutionStrategy.INNER, repr=False, converter=ResolutionStrategy)

    _v_hash: int = attr.ib(init=False, repr=False)
    @_v_hash.default
    def _init_v_hash(self):
        return hash(self.path)

    _injector_class: type[Injector] = attr.ib(kw_only=True, default=Injector, repr=False)
    
    _key_class: type[DepKey] = attr.ib(init=False, repr=True)
    @_key_class.default
    def _init_graph(self):
        @attr.s(slots=True, frozen=True, cmp=True, cache_hash=True)
        class ScopeDepKey(DepKey):
            container: Container = attr.ib(default=self.container)
            strategy: Container = attr.ib(default=self.strategy)
            scope = self
        return ScopeDepKey

    graph: nx.DiGraph = attr.ib(init=False, repr=True)
    @graph.default
    def _init_graph(self):
        g = nx.DiGraph()
        g.add_edges_from(self.container._dro_entries_())
        return nx.freeze(g)

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

    def __bool__(self):
        return True
 
    @t.overload
    def depkey(self, abstract: Injectable, source: Container=..., strategy: ResolutionStrategy=...): ...
    def depkey(self, abstract: Injectable, *a, **kw):
        return self._key_class(abstract, *a, **kw)

    def dro_inner(self, abstract: Injectable, source: Container, *, skip_source: bool=False, depth: int=None):
        ioc: Container
        g = self.graph
        if source in g:
            if not skip_source:
                yield from source[abstract]
            for n, ioc in nx.bfs_edges(g, source, depth_limit=depth):
                yield from ioc[abstract]

    def dro_outer(self, abstract: Injectable, source: Container, *, skip_source: bool=False, depth: int=None):
        ioc: Container
        g = self.graph
        if source in g:
            if not skip_source:
                yield from source[abstract]
            for n, ioc in nx.bfs_edges(g, source, reverse=True, depth_limit=depth):
                yield from ioc[abstract]

    def dro(self, key):
        abstract, source, strategy = key
        if strategy & ResolutionStrategy.INNER:
            yield self.dro_inner(abstract, source)

        if strategy & ResolutionStrategy.OUTER:
            yield self.dro_outer(abstract, source)

        if strategy & ResolutionStrategy.UPPER:
            yield from self.parent.dro(key) 

    def __missing__(self, key: t.Union[DepKey, tuple]) -> t.Union[Dependency, None]:
        if isinstance(key, DepKey):
            it = self.dro(key)
            if pro := next(it, None):
                return self.__setdefault(key, pro.compose(self, key, it))
            elif dep := self.parent[key]:
                return self.__setdefault(key, dep)
        elif dep := self[self.depkey(*key)]:
            return self.__setdefault(key, dep)

    # def _resolve_dependency(
    #     self,
    #     key: Injectable,
    #     container: "Container" = None,
    #     loc: '_ContainerContext' = _ContainerContext.GLOBAL,
    #     *,
    #     only_self: bool = True,
    # ):
    #     if container := self.container.get_container(container):
    #         ident = container, loc
    #         resolved = self._resolved[key]
    #         if ident in resolved:
    #             return resolved[ident]

    #         if isinstance(key, Provider):
    #             pros = [key]
    #         else:
    #             ns = container.get_registry(loc)
    #             pros = ns.get_all(key)
    #             if not pros and (origin := t.get_origin(key)):
    #                 pros = ns.get_all(origin)
    #         if pros:
    #             if pro := pros[0].compose(self, key, *pros[1:]):
    #                 return resolved.setdefault(ident, pro)

    #         if not (container is self.container or loc is _ContainerContext.LOCAL):
    #             if dp := self._resolve_dependency(key, None, loc, only_self=True):
    #                 resolved[ident] = dp
    #                 return dp

    #         if not container.parent and loc is _ContainerContext.LOCAL:
    #             return
    #         container = container.parent

    #     if not only_self:
    #         return self.parent._resolve_dependency(key, container, loc, only_self=False)

    def injector(self, parent: t.Union[Injector, None] = NullInjectorContext()):
        if self.parent and not (parent and self.parent in parent):
            parent = self.parent.injector(parent)
        elif parent and self in parent:
            raise TypeError(f"Injector {parent} in scope.")

        return self.create_injector(parent)

    def create_injector(self, parent: Injector = NullInjectorContext()):
        return self._injector_class(parent, self)

    def __eq__(self, o) -> bool:
        if isinstance(o, Scope):
            return o.path == self.path 
        return NotImplemented

    def __ne__(self, o) -> bool:
        if isinstance(o, Scope):
            return o.path != self.path 
        return NotImplemented

    def __hash__(self):
        return self._v_hash






class NullRootScope(Scope):
    __slots__ = ()
    parent = None
    container = frozendict()
    graph = nx.freeze(nx.DiGraph())

    level = -1
    path = ()
    _v_hash = hash(path)

    def iproviders(self, key):
        if False: yield

    def __init__(self) -> None: ...

    def __bool__(self): 
        return False
    def __repr__(self): 
        return f'{self.__class__.__name__}()'
    def __contains__(self, key): 
        return False
    def __getitem__(self, key): 
        return None
        