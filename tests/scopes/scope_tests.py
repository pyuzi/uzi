from inspect import isfunction
import typing as t
from unittest.mock import patch
import attr
import pytest


from collections import abc


from uzi.containers import Container
from uzi.exceptions import InjectorError
from uzi.graph import DepGraph, _null_graph
from uzi.injectors import Injector
from uzi.scopes import Scope


from .. import checks

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



_T = t.TypeVar('_T')
_T_FnNew = abc.Callable[..., Scope]


@pytest.fixture
def new_args(MockContainer: type[DepGraph]):
    return MockContainer(),

@pytest.fixture
def cls():
    return Scope



@pytest.fixture
def immutable_attrs(cls):
    return [a for a in dir(cls) if not (a[:2] == '__' == a[-2:] or isfunction(getattr(cls, a)))]


test_immutable = checks.is_immutable




def test_basic(new: _T_FnNew):
    sub = new()
    str(sub)
    assert isinstance(sub, Scope)
    assert isinstance(sub.parent, Scope)
    assert isinstance(sub.graph, DepGraph)
    assert isinstance(sub.container, Container)


def test_compare(new: _T_FnNew):
    sub = new()
    cp = new(sub.graph, sub.parent)
    assert cp.graph is sub.graph
    assert cp.parent is sub.parent
    assert sub != cp
    assert not sub == cp
    assert sub != object()
    assert not sub == object()
    assert hash(sub) != hash(cp)


def test_create_with_graph(new: _T_FnNew, MockGraph: DepGraph):
    graph = MockGraph()
    graph.parent = _null_graph
    sub = new(graph)
    assert sub.graph is graph
    

@xfail(raises=ValueError, strict=True)
def test_with_parent_graph_mismatch(new: _T_FnNew, MockGraph: DepGraph):
    sub = new(MockGraph())
    

@xfail(raises=TypeError, strict=True)
def test_create_with_other_object(new: _T_FnNew):
    sub = new(object())
    


def test__set_current(new: _T_FnNew, MockInjector):
    sub, inj = new(), MockInjector()
    sub._set_current_injector(inj)
    assert sub.current is inj
    

def test_new_injector(new: _T_FnNew, cls: type[Scope], MockScope, MockInjector):
    with patch.object(cls, '_injector_class', spec=type[Injector]):
        cls._injector_class.return_value = inj = MockInjector()
        parent=MockScope()
        sub = new(parent=parent)
        assert inj is sub._new_injector()
        sub._injector_class.assert_called_once_with(sub.graph, sub.parent.injector())


def test_setup_reset(new: _T_FnNew, cls: type[Scope], MockInjector):
    with patch.object(cls, '_new_injector'):
        cls._new_injector.return_value = inj = MockInjector()
        initial = MockInjector()
        sub = new(initial=initial)

        assert not sub.is_active
        assert sub.current is sub.initial is initial
        
        res = sub.setup()
        assert isinstance(res, Injector)
        assert inj is res
        assert inj is sub.current
        assert sub.is_active

        sub.reset()
        assert not sub.is_active
        assert sub.current is sub.initial is initial

        sub._new_injector.assert_called_once()

def test_setup_reset_multiple_times(new: _T_FnNew, cls: type[Scope], MockInjector):
    with patch.object(cls, '_new_injector'):
        cls._new_injector.return_value = inj = MockInjector()
        initial = MockInjector()
        sub = new(initial=initial)
        N = 4

        assert not sub.is_active
        assert sub.current is sub.initial is initial
        for _ in range(N):
            res = sub.setup()
            assert sub.is_active and inj is res is sub.current
            sub.reset()
            assert not sub.is_active and sub.current is sub.initial is initial

        sub._new_injector.assert_called()
        assert sub._new_injector.call_count == N


@xfail(raises=InjectorError, strict=True)
def test_setup_multiple_times(new: _T_FnNew, cls: type[Scope], MockInjector):
    with patch.object(cls, '_new_injector', spec=Injector):
        cls._new_injector = MockInjector
        sub = new()
        assert not sub.is_active
        sub.setup()
        assert sub.is_active
        sub.setup()
        

@xfail(raises=InjectorError, strict=True)
def test_reset_multiple_times(new: _T_FnNew, cls: type[Scope], MockInjector):
    with patch.object(cls, '_new_injector', spec=Injector):
        cls._new_injector = MockInjector
        sub = new()
        assert not sub.is_active
        sub.setup()
        assert sub.is_active
        sub.reset()
        assert not sub.is_active
        sub.reset()


def test_injector(new: _T_FnNew, cls: type[Scope], MockInjector):
    with patch.object(cls, '_new_injector', spec=Injector):
        cls._new_injector = MockInjector
        N, sub = 3, new()
        assert not sub.is_active
        res = sub.injector()
        assert isinstance(res, Injector)
        assert sub.is_active

        for _ in range(N):
            assert sub.injector() is res is sub.current
        
        assert sub.injector(setup=False) is res is sub.current
        
        sub._new_injector.assert_called_once()

        sub.reset()
        assert not sub.is_active

        for _ in range(N):
            assert not sub.injector(setup=False) is sub.current
            assert not sub.is_active

        assert sub._new_injector.call_count == N + 1

        
def test_as_contextmanager(new: _T_FnNew, cls: type[Scope], MockInjector):
    with patch.object(cls, '_new_injector', spec=Injector):
        cls._new_injector.return_value = inj = MockInjector()
        sub = new()
        assert not sub.is_active
        with sub as io:
            assert sub.is_active
            assert io is inj is sub.current
        assert not sub.is_active


def test_as_contextmanager_after_setup(new: _T_FnNew, cls: type[Scope], MockInjector):
    with patch.object(cls, '_new_injector', spec=Injector):
        cls._new_injector.return_value = inj = MockInjector()
        sub = new()
        assert not sub.is_active
        inj_ = sub.setup()
        assert sub.is_active
        with sub as io:
            assert sub.is_active
            assert io is inj is inj_ is sub.current
        assert not sub.is_active


