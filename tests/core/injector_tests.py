from copy import copy
import typing as t
from unittest.mock import MagicMock
import attr
import pytest


from collections.abc import Callable, Iterator, Set, MutableSet
from xdi.exceptions import InjectorLookupError
from xdi._common import FrozenDict
from xdi.injectors import Injector, NullInjector, _null_injector
from xdi._bindings import SimpleBinding, Binding, LookupErrorBinding


from xdi.graph import NullGraph, DepGraph



from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')

_T_FnNew = Callable[..., Injector]

_T_Miss =  t.TypeVar('_T_Miss')



class InjectorTests(BaseTestCase[Injector]):

    @pytest.fixture
    def mock_graph(self, mock_graph):
        mock_graph[_T_Miss] = LookupErrorBinding(_T_Miss, mock_graph)
        return mock_graph

    @pytest.fixture
    def new_args(self, mock_graph):
        return mock_graph, _null_injector,

    def test_basic(self, new: _T_FnNew):
        sub = new()
        assert isinstance(sub, Injector)
        assert isinstance(sub.graph, DepGraph)
        assert isinstance(sub.parent, Injector)
        assert sub
        str(sub),
        
    def test_compare(self, new: _T_FnNew):
        sub = new()
        assert sub == copy(sub)
        assert not sub == object()
        assert sub != object()
    
    def test_immutable(self, new: _T_FnNew, immutable_attrs):
        self.assert_immutable(new(), immutable_attrs)

    @xfail(raises=(InjectorLookupError, TypeError), strict=True)
    @parametrize('key', [
        _T_Miss, 
        SimpleBinding(_T_Miss, NullGraph(), concrete=MagicMock(_T_Miss))
    ])
    def test_lookup_error(self, new: _T_FnNew, key):
        sub = new()
        assert not key in sub
        if isinstance(key, Binding):
            sub[key]
        else:
            sub.make(key)

   
       