import asyncio
import typing as t

import pytest
from xdi import Dep
from xdi.providers import AnnotatedProvider as Provider

from .abc import ProviderTestCase, AsyncProviderTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_Ta = t.TypeVar("_Ta")


class AnnotatedProviderTests(ProviderTestCase):
    @pytest.fixture
    def provider(self):
        return Provider(t.Annotated[t.Any, _Ta])

    @pytest.fixture
    def scope(self, scope, value_setter):
        scope[_Ta] = lambda inj: value_setter
        return scope




class AsyncAnnotatedProviderTests(AnnotatedProviderTests, AsyncProviderTestCase):

    
    @pytest.fixture
    def scope(self, scope, value_setter):
        fn = lambda inj: value_setter
        fn.is_async = True
        scope[_Ta] = fn
        return scope

