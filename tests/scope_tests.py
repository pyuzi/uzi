from itertools import chain
from os import sep
import typing as t
import attr
import pytest
import networkx as nx

from unittest.mock import  Mock

from collections.abc import Callable, Iterator
from xdi._common.collections import frozendict


from xdi.containers import Container
from xdi.providers import Provider
from xdi.scopes import NullRootScope, Scope



from .abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_T_Scp = t.TypeVar('_T_Scp', bound=Scope)

_T_FnNew = Callable[..., _T_Scp]

        


class NullRootScopeTests(BaseTestCase[NullRootScope]):

    type_: t.ClassVar[type[_T_Scp]] = NullRootScope

    def test_basic(self, new: _T_FnNew):
        sub = new()
        assert isinstance(sub, NullRootScope)
        assert isinstance(sub, frozendict)
        assert isinstance(sub.graph, nx.DiGraph)
        assert nx.is_frozen(sub.graph)
        assert sub.parent is None
        assert sub.level == -1
        assert not sub
        assert not sub.container
        assert not sub.graph
        str(sub)
        
    def test_compare(self, new: _T_FnNew):
        sub = new()
        assert sub == NullRootScope()
        assert not sub != NullRootScope()
        assert not sub is NullRootScope()
        assert hash(sub) == hash(NullRootScope())

    def test_is_blank(self, new: _T_FnNew):
        sub = new()
        assert len(sub) == 0
        assert sub[_T] is None
        assert not _T in sub



class ScopeTest(BaseTestCase[_T_Scp]):

    type_: t.ClassVar[type[_T_Scp]] = Scope

    @pytest.fixture
    def MockContainer(self):
        x = 0
        def make(name='mock', *a, **kw):
            nonlocal x
            x += 1
            mi: Container = Mock(spec=Container, name=f'{name}')
            mi._dro_entries_ = Mock(return_value=[(mi, mi)])
            mi.__getitem__ = Mock(return_value=[mi,])
            # mi.__gt__ = Mock(wraps=x.__gt__)
            # mi.__ge__ = Mock(wraps=x.__ge__)
            # mi.__lt__ = Mock(wraps=x.__lt__)
            # mi.__le__ = Mock(wraps=x.__le__)
            mock = Mock(spec=type[Container], return_value=mi)
            return mock(name, *a, **kw)
        return make

    @pytest.fixture
    def new_args(self, MockContainer: type[Container]):
        return MockContainer(),

    def test_basic(self, new: _T_FnNew):
        sub = new()
        assert isinstance(sub, Scope)
        assert isinstance(sub, frozendict)
        assert isinstance(sub.container, Container)
        assert isinstance(sub.parent, NullRootScope)
        assert isinstance(sub.graph, nx.DiGraph)
        assert sub
        assert len(sub) == 0
        assert not sub.parent
        assert sub.level == 0
        str(sub)
    
    def test_container(self, new: _T_FnNew, MockContainer: type[Container]):
        container = MockContainer()
        sub = new(container)
        assert container
        assert isinstance(container, Container)
        assert sub.container is container
        assert sub.name == container.name
    
    def test_immutable(self, new: _T_FnNew):
        sub = new()
        for atr in attr.fields(sub.__class__):
            try:
                sub.__setattr__(atr.name, getattr(sub, atr.name, None))
            except AttributeError:
                continue
            else:
                raise AssertionError(f"mutable: {atr.name!r} -> {sub}")
        
    def test_parent(self, new: _T_FnNew, MockContainer: type[Container]):
        sub = new(MockContainer())
        assert not sub.parent
        assert sub.level == 0
        sub2 = new(MockContainer(), sub)
        assert sub2.parent is sub
        assert sub2.level == 1     

    def test_compare(self, new: _T_FnNew, container, MockContainer: type[Container]):
        sub1, sub2 = new(container), new(container),
        assert sub1.container is container is sub2.container
        assert sub1 == sub2 and not (sub1 != sub2)
        assert sub1 != container and not(sub1 == container)
        assert hash(sub1) == hash(sub2)

        c2 = MockContainer()
        sub11, sub22, sub3 = new(c2, sub1), new(c2, sub2), new(MockContainer(), sub2)
        assert sub11 == sub22
        assert sub11 != sub3 
        assert sub22 != sub3 
           
    def test_parents(self, new: _T_FnNew, MockContainer: type[Container]):
        sub1 = new(MockContainer())
        sub2 = new(MockContainer(), sub1)
        sub3 = new(MockContainer(), sub2)
        sub4 = new(MockContainer(), sub3)

        assert sub4.level == 3
        
        it = sub4.parents()
        assert isinstance(it, Iterator)
        assert tuple(it) == (sub3, sub2, sub1)
        
    def test_graph_basic(self, new: _T_FnNew, MockContainer: type[Container]):
        container = MockContainer()
        sub = new(container)
        assert sub.container is container
        assert isinstance(sub.graph, nx.DiGraph)
        assert nx.is_frozen(sub.graph)
        assert [*sub.graph.edges] == [(container, container)]
        container._dro_entries_.assert_called_once_with()
      
    def test_graph_nodes(self, new: _T_FnNew, MockContainer: type[Container]):
        c1, c2, c3, c4, c5, c6 = (MockContainer(f'ioc{i:02d}') for i in range(1, 7))
        edges = [(c4, c6), (c4, c5), (c2, c4), (c1, c2), (c3, c5), (c1, c3), (c1, c1)]
        c1._dro_entries_ = Mock(wraps=lambda: iter(edges))
        sub = new(c1)
        g = nx.DiGraph()
        g.add_edges_from(edges)
        assert sub.container is c1
        assert sub.graph.nodes == g.nodes
        assert sub.graph.edges == g.edges
        # assert (*sub.graph.nodes,) == (*dict.fromkeys(chain(*edges)),)
        
    def test_dro_inner(self, new: _T_FnNew,  MockContainer: type[Container]):
        c1, c2, c3, c4, c5, c6 = (MockContainer(f'ioc{i:02d}') for i in range(1, 7))
        edges = [
            (c1, c1),
            (c1, c3),
            (c3, c5),
            (c1, c2),
            (c2, c4),
            (c4, c6),
            (c4, c5),
        ]
        c1._dro_entries_ = Mock(wraps=lambda: iter(edges))

        g = nx.DiGraph(edges)

        for c in (c1, c2, c3, c4, c5, c6):
            c.__getitem__ = Mock(return_value=[c])

        sub = new(c1)
        print('', *edges, sep='\n - ')

        it = sub.dro_inner(_T, c1)
        assert isinstance(it, Iterator)
        it = tuple(it)
        print('', *it, sep='\n - ')
        print('', *(c6, c5, c4, c5, c3, c1), sep='\n - ')
        assert it == (c1, c3, c2, c5, c4, c6)



    def test_getitem(self, new):
        pass


    