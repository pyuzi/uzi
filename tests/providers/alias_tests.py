import asyncio
from unittest.mock import MagicMock, Mock
import pytest
import typing as t




from xdi.providers import Alias as Provider
from xdi._bindings import Binding
from xdi.graph import DepGraph


from .abc import ProviderTestCase, AsyncProviderTestCase, _T_NewPro



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



_Ta = t.TypeVar('_Ta')


class AliasProviderTests(ProviderTestCase[Provider]):

    @pytest.fixture
    def concrete(self):
        return _Ta

    def test_resolve(self, cls, abstract, concrete, new: _T_NewPro, mock_scope: DepGraph):
        subject, res = super().test_resolve(cls, abstract, new, mock_scope)
        mock_scope.__getitem__.assert_called_once_with(concrete)
        





# class AsyncAliasProviderTests(AliasProviderTests, AsyncProviderTestCase):

#     @pytest.fixture
#     def scope(self, scope, value_setter):
#         fn = lambda inj: value_setter
#         fn.is_async = True
#         scope[_Ta] = fn
#         return scope

