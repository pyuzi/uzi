import asyncio
import pytest

import typing as t



from xdi.providers import UnionProvider as Provider, Factory

from xdi import Scope

 

from .abc import ProviderTestCase, AsyncProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_Ta = t.TypeVar('_Ta')



class UnionProviderTests(ProviderTestCase):
    
    @pytest.fixture
    def provider(self):
        return Provider(t.Union[_T, _Ta])

    @pytest.fixture
    def scope(self, scope, value_setter):
        scope[_Ta] = lambda c: value_setter
        return scope




class AsyncUnionProviderTests(UnionProviderTests, AsyncProviderTestCase):

    @pytest.fixture
    def scope(self, scope, value_setter):
        scope[_Ta] = fn = lambda c: lambda: asyncio.sleep(0, value_setter())
        fn.is_async = True
        return scope

