import typing as t

import pytest
from laza.di import Dep, Call
from laza.di.providers import CallMarkerProvider as Provider
from laza.common.collections import Arguments

from .abc import ProviderTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_Tk = t.TypeVar("_Tk")
_Ta = t.TypeVar("_Ta")


class CallMarkerTests(ProviderTestCase):

    provides =None

    @pytest.fixture
    def provider(self):
        return Provider()

    @pytest.fixture
    def arguments(self):
        return Arguments.make(1,2,3, 456, a='A', b='B', t='Tea')

    @pytest.fixture
    def marker(self, arguments: Arguments):
        return Call(lambda *a, **kw: Arguments(a, kw), 1,2,3, Dep(_Ta, default=456), a='A', b='B', t=Dep(_Tk, default='Tea'))

    @pytest.fixture(autouse=True)
    def set_provides(self, marker, arguments: Arguments):
        self.provides = marker
        self.value = arguments

    def test_provide(self, provider: Provider, injector, context):
        bound =  provider.bind(injector, self.provides)
        func = bound(context)
        val = func()()
        assert self.value == val
        
