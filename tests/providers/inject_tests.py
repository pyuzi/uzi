import pytest

import typing as t



from laza.di.providers import InjectProvider as Provider

from laza.di.common import Inject
from laza.di.injectors import Injector
 

from .abc import ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_Ta = t.TypeVar('_Ta')
_Tx = t.TypeVar('_Tx')




class InjectProviderTests(ProviderTestCase):
    
    cls = Provider

    @pytest.fixture
    def provider(self):
        return Provider(Inject(_Tx, default=Inject(_Ta)))

    @pytest.fixture
    def context(self, context, value_setter):
        context[_Ta] = value_setter
        return context




