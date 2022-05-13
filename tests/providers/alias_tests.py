import asyncio
from unittest.mock import MagicMock, Mock
import pytest
import typing as t




from uzi.providers import Alias as Provider
from uzi.graph.nodes import Node
from uzi.graph import Graph


from .abc import ProviderTestCase, AsyncProviderTestCase, _T_NewPro



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



_Ta = t.TypeVar('_Ta')


class AliasProviderTests(ProviderTestCase[Provider]):

    @pytest.fixture
    def concrete(self):
        return _Ta

    def test_resolve(self, cls, abstract, concrete, new: _T_NewPro, mock_graph: Graph):
        subject, res = super().test_resolve(cls, abstract, new, mock_graph)
        mock_graph.__getitem__.assert_called_once_with(concrete)
        





# class AsyncAliasProviderTests(AliasProviderTests, AsyncProviderTestCase):

#     @pytest.fixture
#     def graph(self, graph, value_setter):
#         fn = lambda inj: value_setter
#         fn.is_async = True
#         graph[_Ta] = fn
#         return graph

