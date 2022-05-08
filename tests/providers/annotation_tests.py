import asyncio
import typing as t
from unittest import mock
import attr

import pytest
from uzi import Dep, DependencyMarker, is_injectable
from uzi.providers import AnnotationProvider as Provider
from uzi.graph import DepGraph

from .abc import ProviderTestCase, _T_NewPro


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_Ta = t.TypeVar("_Ta")
_Tb = t.TypeVar("_Tb")


_Ann = object()


@attr.s(frozen=True)
class Marker(DependencyMarker):
    name = attr.ib(default='<MARKER>')

    @property
    def __origin__(self):
        return self.__class__



_T_NewPro = _T_NewPro[Provider]


class AnnotationProviderTests(ProviderTestCase[Provider]):

    expected = {
        t.Annotated[_Ta, _Ann, Dep(_Tb), t.Literal['abc'], None]: [
            (Dep(_Tb), _Ta), 
            (Dep(_Tb), _Ta)
        ],   
        t.Annotated[t.Literal['abc'], Dep(_Ta), Provider, Marker()]: [
            (Marker(), Dep(_Ta), t.Literal['abc']),
            (Marker(), Dep(_Ta)),
        ], 
        t.Annotated[Provider, Dep(_Ta), Provider, Marker()]: [
            (Marker(), Dep(_Ta), Provider),
            (Marker(), Dep(_Ta), Provider),
        ],
    }
    
    @pytest.fixture(params=expected.keys())
    def abstract(self, request):
        return request.param

    @pytest.fixture
    def new_args(self):
        return ()

    def test_get_all_args(self, abstract, new: _T_NewPro):
        subject, result = new(), ()
        result = tuple(subject.get_all_args(abstract))
        assert result == self.expected[abstract][0]
        return subject, result

    def test_get_injectable_args(self, abstract, new: _T_NewPro):
        subject, result = new(), ()
        result = tuple(subject.get_injectable_args(abstract))
        assert result == self.expected[abstract][1]
        assert len(result) == len(set(result))
        assert all(is_injectable(a) for a in result)
        return subject, result
        
    def test_resolve(self, cls, abstract, new: _T_NewPro, mock_graph: DepGraph):
        subject, res = super().test_resolve(cls, abstract, new, mock_graph)
        expected = self.expected[abstract][1]
        calls = [mock.call(inj) for inj in  expected]
        mock_graph.__getitem__.mock_calls == calls
        return subject, res




# class AsyncAnnotatedProviderTests(AnnotatedProviderTests, AsyncProviderTestCase):

    
#     @pytest.fixture
#     def graph(self, graph, value_setter):
#         fn = lambda inj: value_setter
#         fn.is_async = True
#         graph[_Ta] = fn
#         return graph

