import asyncio
import pytest

import typing as t



from xdi.providers import UnionProvider as Provider, Factory

from xdi.injectors import Injector

 

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
    def injector(self, injector, value_setter):
        injector.bindings[_Ta] = lambda c: value_setter
        return injector




class AsyncUnionProviderTests(UnionProviderTests, AsyncProviderTestCase):

    @pytest.fixture
    def injector(self, injector, value_setter):
        injector.bindings[_Ta] = fn = lambda c: lambda: asyncio.sleep(0, value_setter())
        fn.is_async = True
        return injector

