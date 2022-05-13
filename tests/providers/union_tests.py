from unittest import mock
import pytest

import typing as t


from uzi.providers import UnionProvider as Provider

from uzi import is_injectable
from uzi.graph.core import Graph


from .abc import ProviderTestCase, _T_NewPro


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_Ta = t.TypeVar("_Ta")
_Tb = t.TypeVar("_Tb")
_Tc = t.TypeVar("_Tc")
_Td = t.TypeVar("_Td")


_T_NewPro = _T_NewPro[Provider]


class UnionProviderTests(ProviderTestCase[Provider]):

    expected = {
        t.Union[_Ta, _Tb, t.Literal["abc"], _Ta, None]: [
            (_Ta, _Tb, t.Literal["abc"], type(None)),
            (_Ta, _Tb),
        ],
        t.Union[t.Literal["abc"], Provider, t.Literal["abc"], _Td]: [
            (t.Literal["abc"], Provider, _Td),
            (Provider, _Td),
        ],
    }

    @pytest.fixture
    def new_args(self):
        return ()

    @pytest.fixture(params=expected.keys())
    def abstract(self, request):
        return request.param

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

    def test_resolve(self, cls, abstract, new: _T_NewPro, mock_graph: Graph):
        subject, res = super().test_resolve(cls, abstract, new, mock_graph)
        expected = self.expected[abstract][1]
        calls = [mock.call(inj) for inj in expected]
        mock_graph.__getitem__.mock_calls == calls
        return subject, res


# class AsyncUnionProviderTests(UnionProviderTests, AsyncProviderTestCase):


#     @pytest.fixture
#     def graph(self, graph, value_setter):
#         fn = lambda inj: value_setter
#         fn.is_async = True
#         graph[_Ta] = fn
#         return graph
