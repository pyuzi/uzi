from collections import abc
from copy import copy, deepcopy
import pickle
import typing as t
from unittest.mock import MagicMock
import attr
import pytest


from uzi.exceptions import InjectorLookupError
from uzi.injectors import Injector, _null_injector
from uzi.graph.nodes import SimpleNode, Node, MissingNode


from uzi.graph.core import NullGraph, Graph


from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar("_T")

_T_FnNew = abc.Callable[..., Injector]

_T_Miss = t.TypeVar("_T_Miss")


class InjectorTests(BaseTestCase[Injector]):
    @pytest.fixture
    def mock_graph(self, mock_graph):
        mock_graph[_T_Miss] = MissingNode(_T_Miss, mock_graph)
        return mock_graph

    @pytest.fixture
    def new_args(self, mock_graph):
        return (
            mock_graph,
            _null_injector,
        )

    def test_basic(self, new: _T_FnNew):
        sub = new()
        assert isinstance(sub, Injector)
        assert isinstance(sub.graph, Graph)
        assert isinstance(sub.parent, Injector)
        assert isinstance(sub.bound(_T), abc.Callable)
        assert sub
        str(sub), hash(sub)

    def test_compare(self, new: _T_FnNew):
        sub = new()
        assert sub is copy(sub)
        assert not sub == object()
        assert sub != object()

    @xfail(raises=TypeError, strict=True)
    def test_deepcopy(self, new: _T_FnNew):
        sub = new()
        deepcopy(sub)

    @xfail(raises=TypeError, strict=True)
    def test_pickle(self, new: _T_FnNew):
        sub = new()
        pickle.dumps(sub)

    def test_immutable(self, new: _T_FnNew, immutable_attrs):
        self.assert_immutable(new(), immutable_attrs)

    @xfail(raises=(InjectorLookupError, TypeError), strict=True)
    @parametrize(
        "key", [_T_Miss, SimpleNode(_T_Miss, NullGraph(), concrete=MagicMock(_T_Miss))]
    )
    def test_lookup_error(self, new: _T_FnNew, key):
        sub = new()
        assert not key in sub
        if isinstance(key, Node):
            sub[key]
        else:
            sub.make(key)
