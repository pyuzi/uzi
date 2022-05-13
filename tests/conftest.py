import asyncio
from inspect import isfunction
import operator
from unittest.mock import MagicMock, Mock, NonCallableMagicMock
import pytest
import typing as t
from uzi import is_injectable
from uzi.containers import Container, Group
from uzi.markers import Injectable
from uzi.injectors import Injector
from uzi.markers import ProPredicate
from uzi.providers import Provider

from uzi.graph.nodes import Node
from uzi.graph.core import Graph, DepKey, DepSrc
from uzi.scopes import Scope


@pytest.fixture
def new_args():
    return ()


@pytest.fixture
def new_kwargs():
    return {}


@pytest.fixture
def new(cls, new_args, new_kwargs):
    return lambda *a, **kw: cls(*a, *new_args[len(a) :], **{**new_kwargs, **kw})


# @pytest.fixture
# def immutable_attrs(cls):
#     return ()


@pytest.fixture
def immutable_attrs(cls):
    return [
        a
        for a in dir(cls)
        if not (a[:2] == "__" == a[-2:] or isfunction(getattr(cls, a)))
    ]


@pytest.fixture
def value_factory_spec():
    return object


@pytest.fixture
def value_factory(value_factory_spec):
    return MagicMock(value_factory_spec, wraps=value_factory_spec)


@pytest.fixture
def MockContainer(request: pytest.FixtureRequest):
    def make(**kw):
        mi: Container = NonCallableMagicMock(Container)
        mi.pro = (mi,)
        mi.__bool__.return_value = True
        mi.__hash__.return_value = id(mi)
        mi.__getitem__.return_value = None
        mi.is_atomic = True
        mi.atomic = {mi}
        mi._resolve = MagicMock(
            wraps=lambda k, s: tuple(filter(None, [mi[getattr(k, "abstract", k)]]))
        )  # mi.__getitem__

        kw.setdefault("module", request.module.__name__)
        kw.setdefault("name", "test")
        kw.setdefault("qualname", f"{kw['module']}:{kw['name']}")
        kw.setdefault("_is_anonymous", False)

        G = {}

        def mock_graph(k):
            if k in G:
                return G[k]
            mg = MagicMock(Graph)
            mg.container = mi
            mg.parent = k
            return G.setdefault(k, mg)

        mi.get_graph = MagicMock(wraps=mock_graph)

        for k, v in kw.items():
            setattr(mi, k, v)

        return mi

    return MagicMock(type[Container], wraps=make)


@pytest.fixture
def MockGroup(MockContainer, request: pytest.FixtureRequest):
    def make(**kw):
        mi: Group = NonCallableMagicMock(Group)
        mi.pro = mi.atomic = dict.fromkeys(MockContainer() for _ in range(3))
        mi.__bool__.return_value = True
        mi.__hash__.return_value = id(mi)
        mi.is_atomic = False
        mi._resolve = MagicMock(
            wraps=lambda k, s: tuple(filter(None, [mi[getattr(k, "abstract", k)]]))
        )  # mi.__getitem__

        kw.setdefault("module", request.module.__name__)
        kw.setdefault("name", f"test")
        kw.setdefault("qualname", f"{kw['module']}:{kw['name']}")
        kw.setdefault("_is_anonymous", not kw["name"])

        G = {}

        def mock_graph(k):
            if k in G:
                return G[k]
            mg = MagicMock(Graph)
            mg.container = mi
            mg.parent = k
            return G.setdefault(k, mg)

        mi.get_graph = MagicMock(wraps=mock_graph)

        for k, v in kw.items():
            setattr(mi, k, v)

        return mi

    return MagicMock(type[Group], wraps=make)


@pytest.fixture
def MockNode():
    def make(abstract=None, graph=None, **kw):
        mk = MagicMock(Node)

        if not abstract is None:
            kw["abstract"] = abstract

        if not graph is None:
            kw["graph"] = graph

        kw.setdefault("is_async", False)

        for k, v in kw.items():
            setattr(mk, k, v)
        return mk

    return MagicMock(type[Node], wraps=make)


@pytest.fixture
def MockInjector(MockGraph):
    def make(spec=Injector, *, graph=None, parent=True, **kw):
        mi: Injector = MagicMock(spec, **kw)
        mi.__bool__.return_value = True
        mi.graph = graph or MockGraph()

        def mock_dep(k):
            if getattr(k, "is_async", False):
                mk = MagicMock(asyncio.sleep)
            else:
                mk = MagicMock(t.Callable)
            return mk

        deps = {}
        mi.__getitem__ = Mock(
            wraps=lambda k: deps.get(k) or deps.setdefault(k, mock_dep(k))
        )
        mi.__setitem__ = Mock(wraps=lambda k, v: deps.__setitem__(k, v))

        for k, v in kw.items():
            setattr(mi, k, v)

        return mi

    return MagicMock(type[Injector], wraps=make)


@pytest.fixture
def MockProvider(MockNode):
    def make(spec=Provider, **kw):
        mi: Provider = MagicMock(spec, **kw)
        deps = {}

        def mock_dep(a, s):
            if not (a, s) in deps:
                deps[a, s] = MockNode(a, s, provider=mi)
            return deps[a, s]

        mi._resolve = MagicMock(wraps=mock_dep)
        mi.container = None
        mi._setup = MagicMock(
            wraps=lambda c, a=None: (mi.container and mi)
            or setattr(mi, "container", c)
            or mi
        )
        for k, v in kw.items():
            setattr(mi, k, v)

        return mi

    return MagicMock(type[Provider], wraps=make)


@pytest.fixture
def MockScope(MockGraph: type[Graph]):
    def make(spec=Scope, *, parent=True, **kw):
        mi: Scope = NonCallableMagicMock(spec, **kw)

        if parent:
            kw["parent"] = parent = (
                make(parent=parent - 1) if parent is True else parent
            )

        if not "graph" in kw:
            kw["graph"] = MockGraph(parent=parent and parent.graph or None)

        if not "container" in kw:
            kw["container"] = kw["graph"].container

        for k, v in kw.items():
            setattr(mi, k, v)

        return mi

    return MagicMock(type[Container], wraps=make)


@pytest.fixture
def MockGraph(MockContainer, MockNode):
    def make(*, parent=True, **kw):
        mi: Graph = NonCallableMagicMock(Graph)

        deps = {}

        def getitem(k):
            if k in deps:
                return deps[k]
            elif not isinstance(k, DepKey):
                return deps.setdefault(k, getitem(DepKey(k, mi.container)))

            return deps.setdefault(k, MockNode(abstract=k, graph=mi))

        if parent:
            kw["parent"] = parent = (
                make(parent=parent - 1) if parent is True else parent
            )

        if not "container" in kw:
            kw["container"] = MockContainer()

        if not "__contains__" in kw:
            kw["__contains__"] = MagicMock(
                operator.__contains__, wraps=lambda k: deps.get(k) or is_injectable(k)
            )

        if not "__getitem__" in kw:
            kw["__getitem__"] = MagicMock(operator.getitem, wraps=getitem)

        if not "__setitem__" in kw:
            kw["__setitem__"] = MagicMock(operator.setitem, wraps=deps.__setitem__)

        for k, v in kw.items():
            setattr(mi, k, v)

        return mi

    return MagicMock(type[Graph], wraps=make)


@pytest.fixture
def MockProPredicate():
    def make(spec=ProPredicate, **kw):
        mi = NonCallableMagicMock(spec)

        for k, v in kw.items():
            setattr(mi, k, v)

        return mi

    return MagicMock(type[ProPredicate], wraps=make)


@pytest.fixture
def MockDepKey(MockDepSrc):
    def make(spec=DepKey, **kw):
        mi: DepKey = NonCallableMagicMock(spec)
        mi.abstract = Mock(Injectable)
        mi.src = src = MockDepSrc()
        mi.container = src.container
        mi.predicate = src.predicate
        mi.graph = src.graph

        for k, v in kw.items():
            setattr(mi, k, v)
        return mi

    return MagicMock(type[DepKey], wraps=make)


@pytest.fixture
def MockDepSrc(mock_graph, mock_pro_predicate):
    def make(spec=DepSrc, **kw):
        mi: DepSrc = MagicMock(spec)
        mi.container = mock_graph.container
        mi.graph = mock_graph
        mi.predicate = mock_pro_predicate

        for k, v in kw.items():
            setattr(mi, k, v)
        return mi

    return MagicMock(type[DepSrc], wraps=make)


@pytest.fixture
def mock_container(MockContainer):
    return MockContainer()


@pytest.fixture
def mock_graph(mock_scope):
    return mock_scope.graph


@pytest.fixture
def mock_scope(MockScope):
    return MockScope()


@pytest.fixture
def mock_provider(MockProvider):
    return MockProvider()


@pytest.fixture
def mock_injector(MockInjector, MockScope):
    scope = MockScope()
    return MockInjector(scope=scope, graph=scope.graph)


@pytest.fixture
def mock_pro_predicate(MockProPredicate):
    return MockProPredicate()
