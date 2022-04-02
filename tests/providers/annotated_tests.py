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
        return Provider(t.Annotated[t.Any, Dep(_Ta)])

    @pytest.fixture
    def context(self, context, value_setter):
        context[_Ta] = value_setter
        return context



class AsyncAnnotatedProviderTests(AnnotatedProviderTests, AsyncProviderTestCase):

    @pytest.fixture
    def context(self, context, value_setter):
        context[_Ta] = lambda: asyncio.sleep(0, value_setter())
        return context
       