from copy import copy
import typing as t
from unittest.mock import MagicMock
import pytest


from collections import abc
from uzi.exceptions import InjectorLookupError
from uzi.graph.nodes import SimpleNode
from uzi.injectors import Injector, NullInjector


from uzi.graph.core import NullGraph, Graph


from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar("_T")
_T_Inj = t.TypeVar("_T_Inj", bound=NullInjector)

_T_FnNew = abc.Callable[..., _T_Inj]


class NullInjectorTests(BaseTestCase[NullInjector]):
    def test_basic(self, new: _T_FnNew):
        sub = new()
        assert isinstance(sub, Injector)
        assert isinstance(sub, NullInjector)
        assert isinstance(sub.graph, Graph)
        assert sub.parent is None
        assert not sub
        assert not sub.graph
        str(sub)

    def test_compare(self, new: _T_FnNew):
        sub = new()
        assert sub == new() == copy(sub)
        assert not sub != new()
        assert not sub == object()
        assert sub != object()
        assert hash(sub) == hash(new())

    def test_is_blank(self, new: _T_FnNew):
        sub = new()
        assert len(sub) == 0
        assert not _T in sub

    def test_immutable(self, new: _T_FnNew, immutable_attrs):
        self.assert_immutable(new(), immutable_attrs)

    @xfail(raises=InjectorLookupError, strict=True)
    @parametrize("key", [_T, SimpleNode(_T, NullGraph(), concrete=MagicMock())])
    def test_lookup_error(self, new: _T_FnNew, key):
        new()[key]
