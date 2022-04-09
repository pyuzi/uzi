import asyncio
import pytest
import typing as t




from xdi.providers import Alias as Provider

from .abc import ProviderTestCase, AsyncProviderTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



_Ta = t.TypeVar('_Ta')


class AliasProviderTests(ProviderTestCase):

    @pytest.fixture
    def provider(self):
        return Provider(type, _Ta)

    @pytest.fixture
    def scope(self, scope, value_setter):
        scope[_Ta] = lambda inj: value_setter
        return scope



class AsyncAliasProviderTests(AliasProviderTests, AsyncProviderTestCase):

    @pytest.fixture
    def scope(self, scope, value_setter):
        fn = lambda inj: value_setter
        fn.is_async = True
        scope[_Ta] = fn
        return scope

