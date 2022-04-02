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
    def context(self, context, value_setter):
        context[_Ta] = value_setter
        return context



class AsyncAliasProviderTests(AliasProviderTests, AsyncProviderTestCase):

    @pytest.fixture
    def context(self, context, value_setter):
        context[_Ta] = fn = lambda: asyncio.sleep(0, value_setter())
        fn.is_async = True
        return context
       