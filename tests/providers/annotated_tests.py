import typing as t

import pytest
from laza.di import Dep
from laza.di.providers import AnnotatedProvider as Provider

from .abc import ProviderTestCase

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
