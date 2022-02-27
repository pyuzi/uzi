import pytest

import typing as t



from laza.di.providers import AnnotatedProvider as Provider

from laza.di.common import Inject
 

from .abc import ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_Ta = t.TypeVar('_Ta')




class AnnotatedProviderTests(ProviderTestCase):
    
    @pytest.fixture
    def provider(self):
        return Provider(t.Annotated[t.Any, Inject(_Ta)])

    @pytest.fixture
    def context(self, context, value_setter):
        context[_Ta] = value_setter
        return context

