import typing as t
from collections import abc
from contextvars import ContextVar
from logging import getLogger

from typing_extensions import Self

from .. import Injectable
from .._common import FrozenDict, Missing, ReadonlyDict, private_setattr
from ..exceptions import FinalProviderOverrideError, ProError
from ..markers import (
    ProNoopPredicate,
    ProPredicate,
    _noop_pred,
    is_dependency_marker,
    is_injectable,
)
from .nodes import MissingNode, _T_Node

if t.TYPE_CHECKING:  # pragma: no cover
    from ..containers import Container
    from ..providers import Provider
    from ..scopes import Scope


logger = getLogger(__name__)

_T_Pro = tuple["Container"]
_T_BindKey = t.Union["DepKey", Injectable]

_object_new = object.__new__


class DepSrc(t.NamedTuple):
    graph: "Graph"
    container: "Container"
    predicate: ProPredicate = _noop_pred


@private_setattr
class DepKey:

    __slots__ = (
        "abstract",
        "src",
        "_ash",
    )

    abstract: Injectable
    src: DepSrc

    graph: "Graph" = None

    def __init_subclass__(cls, scope=None) -> None:
        cls.graph = scope
        return super().__init_subclass__()

    def __new__(
        cls: type[Self],
        abstract: Injectable,
        container: "Container" = None,
        predicate: ProPredicate = ProNoopPredicate(),
    ) -> Self:
        self, src = _object_new(cls), DepSrc(
            cls.graph, container, predicate or _noop_pred
        )
        self.__setattr(abstract=abstract, src=src, _ash=hash((abstract, src)))
        return self

    @property
    def container(self):
        return self.src.container

    @property
    def predicate(self):
        return self.src.predicate

    def replace(
        self,
        *,
        abstract: Injectable = None,
        container: "Container" = None,
        predicate: ProPredicate = None,
    ):
        return self.__class__(
            abstract or self.abstract,
            container or self.container,
            predicate or self.predicate,
        )

    def __eq__(self, o) -> bool:
        if isinstance(o, DepKey):
            return o.abstract == self.abstract and o.src == self.src
        return NotImplemented

    def __ne__(self, o) -> bool:
        if isinstance(o, DepKey):
            return o.abstract != self.abstract or o.src != self.src
        return NotImplemented

    def __hash__(self) -> int:
        return self._ash


@private_setattr
class ProPaths(ReadonlyDict[DepSrc, _T_Pro]):
    __slots__ = (
        "graph",
        "pro",
    )

    graph: "Graph"
    pro: FrozenDict["Container", int]

    __contains = dict.__contains__
    __setdefault = dict.setdefault

    def __init__(self, graph: "Graph"):
        base = graph.parent.pros
        pro = {c: i for i, c in enumerate(graph.container.pro) if not c in base}
        if not pro:
            raise ProError(f"{graph.name}")
        self.__setattr(graph=graph, pro=FrozenDict(pro))

    def __contains__(self, x) -> bool:
        return x in self.pro or self.__contains(x)

    def __missing__(self, src: DepSrc):
        pro, graph = tuple(self.pro), self.graph
        src.graph.extends(graph)
        pro = src.predicate.pro_entries(pro, graph, src)
        return self.__setdefault(src, tuple(pro))


@private_setattr
class Graph(ReadonlyDict[_T_BindKey, _T_Node]):
    """An isolated dependency resolution `graph` for a given container.

    Assembles the dependency graphs of dependencies registered in their container.

    Attributes:
        container (Container): The container who's graph we are creating
        parent (Graph): The parent graph. Defaults to None

    Args:
        container (Container): The container who's graph we are creating
        parent (Graph, optional): The parent graph. Defaults to NullGraph

    """

    __slots__ = "container", "parent", "pros", "stack", "keyclass"

    container: "Container"
    parent: Self
    pros: ProPaths
    stack: "ResolutionStack"
    keyclass: type[DepKey]

    __contains = dict.__contains__
    __setdefault = dict.setdefault

    def __init__(self, container: "Container", parent: "Graph" = None):
        self.__setattr(
            container=container,
            parent=_null_graph if parent is None else parent,
            keyclass=type(f"BindKey", (DepKey,), {"graph": self}),
        )
        self.__setattr(
            pros=ProPaths(self),
            stack=ResolutionStack(container),
        )

    @property
    def level(self) -> int:
        return self.parent.level + 1

    @property
    def name(self):
        return self.container.name

    def parents(self):
        """Returns a generetor that iterates over the graph's ancestor starting
        from the current `parent` to the root graph.

        Yields:
            ancestor (Graph): an ancestor.
        """
        parent = self.parent
        while parent:
            yield parent
            parent = parent.parent

    def __bool__(self):
        return True

    def __contains__(self, o) -> bool:
        return self.__contains(o) or o in self.pros or o in self.parent

    def extends(self, graph: Self):
        return graph is self or self.parent.extends(graph)

    def make_key(
        self,
        abstract: Injectable,
        container: "Container" = None,
        predicate: ProPredicate = ProNoopPredicate(),
    ):
        if isinstance(abstract, DepKey):
            return abstract
        else:
            return self.keyclass(
                abstract, container or (self.stack.top.container), predicate
            )

    def find_provider(self, dep: DepKey):
        rv = [p for c in self.pros[dep.src] for p in c._resolve(dep, self)]
        if rv:
            if len(rv) > 1:
                rv.sort(key=lambda p: int(not not p.is_default))
                if final := next((p for p in rv if p.is_final), None):
                    if overrides := rv[: rv.index(final)]:
                        raise FinalProviderOverrideError(dep, final, overrides)
            return rv[0]

    def resolve(self, dep_: _T_BindKey, *, recursive: bool = True):
        if not (bind := self.get(dep_, Missing)) is Missing:
            if recursive or not bind or self is bind.graph:
                return bind
        elif dep_ != (dep := self.make_key(dep_)):
            bind = self.resolve(dep)
            if dep in self:
                bind = self.__setdefault(dep_, bind)
            if recursive or not bind or self is bind.graph:
                return bind
        elif is_injectable(dep.abstract):
            abstract = dep.abstract

            if prov := self.find_provider(dep):

                if prov.container and not prov.container is dep.container:
                    return self.__setdefault(
                        dep, self[self.make_key(abstract, prov.container)]
                    )

                with self.stack.push(prov, abstract):
                    if bind := prov._resolve(abstract, self):
                        return self.__setdefault(dep, bind)
            elif origin := t.get_origin(abstract):
                if is_dependency_marker(origin):
                    if prov := self.find_provider(
                        dep.replace(abstract=t.get_origin(abstract))
                    ):
                        with self.stack.push(prov, abstract):
                            if bind := prov._resolve(abstract, self):
                                return self.__setdefault(dep, bind)
                elif bind := self.resolve(
                    dep.replace(abstract=origin), recursive=False
                ):
                    return self.__setdefault(dep, bind)

            if recursive and ((bind := self.parent[dep]) or dep in self.parent):
                return self.__setdefault(dep, bind)
        else:
            raise TypeError(
                f"expected an `Injectable` not `{dep.abstract.__class__.__qualname__}`"
            )

    __missing__ = resolve

    def __eq__(self, o) -> bool:
        if isinstance(o, Graph):
            return o is self
        return NotImplemented

    def __ne__(self, o) -> bool:
        if isinstance(o, Graph):
            return not o is self
        return NotImplemented

    def __hash__(self):
        return id(self)


class NullGraph(Graph):
    """A 'noop' `Graph` used as the parent of root scopes.

    Attributes:
        container (frozendict):
        parent (None): The parent graph

    Params:
        None

    """

    __slots__ = ()
    parent = None
    container = FrozenDict()
    pros = FrozenDict()
    level = -1
    ident = ()
    _ash = hash(ident)

    name = "<null>"

    def __init__(self) -> None:
        ...  # pragma: no cover

    def extends(self, graph: Self):
        return False

    def __bool__(self):
        return False

    def __repr__(self):
        return f"{self.__class__.__name__}()"

    def __contains__(self, key):
        return False

    def __getitem__(self, key):
        if is_injectable(key):
            return MissingNode(key, self)
        elif isinstance(key, DepKey) and is_injectable(key.abstract):
            return MissingNode(key.abstract, self)
        else:
            raise TypeError(
                f"Graph keys must be `Injectable` not `{key.__class__.__qualname__}`"
            )

    def __eq__(self, o) -> bool:
        return o.__class__ is self.__class__

    def __ne__(self, o) -> bool:
        return not o.__class__ is self.__class__

    __hash__ = classmethod(hash)


_null_graph = NullGraph()


@private_setattr
class ResolutionStack(abc.Sequence):

    __slots__ = ("__var",)

    class StackItem(t.NamedTuple):
        container: "Container"
        abstract: Injectable = None
        provider: "Provider" = None

    __var: ContextVar[tuple[StackItem]]

    def __init__(self, default: "Container"):
        stack = (self.StackItem(default),)
        self.__var = ContextVar(
            f"{default.name}.{self.__class__.__name__}", default=stack
        )
        self.__var.set(stack)

    @property
    def top(self):
        return self[0]

    def push(self, provider: "Provider", abstract: Injectable = None):
        top = self.top
        new = self.StackItem(
            provider.container or top.container,
            abstract or provider.abstract or top.abstract,
            provider,
        )
        self.__var.set((new,) + self[:])
        return self

    def pop(self):
        var = self.__var
        stack = var.get()
        if len(stack) < 2:
            raise ValueError(f"too many calls to pop()")
        var.set(stack[1:])
        return stack[0]

    def index(self, val, start=0, stop=None):
        stack = self.__var.get()[start:stop:]

        if isinstance(val, tuple):
            return stack.index(val)
        else:
            for i, x in enumerate(stack):
                if val in x:
                    return i
        raise ValueError(val)

    def __reversed__(self):
        yield from reversed(self.__var.get())

    def __contains__(self, k):
        stack = self.__var.get()
        if isinstance(k, tuple):
            return k in stack
        else:
            return any(k in x for x in stack)

    def __getitem__(self, k):
        return self.__var.get()[k]

    def __bool__(self):
        return True

    def __len__(self):
        return len(self.__var.get())

    def __iter__(self):
        return iter(self.__var.get())

    def __enter__(self):
        return self

    def __exit__(self, *e):
        self.pop()

    def __copy__(self, *a):
        raise TypeError(f"cannot copy {self.__class__.__qualname__}")

    __deepcopy__ = __reduce__ = __copy__
