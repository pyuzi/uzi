import pytest
import time




from laza.di.providers import Alias as Provider
from laza.di.common import InjectionToken

from .abc import ProviderTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


token = InjectionToken('aliased') 

@pytest.fixture
def provider(injector, scope):
    scope[token] = lambda: f'VALUE FOR [{token=!r}]!'
    return Provider(type, token)




class AliasProviderTests(ProviderTestCase):

    cls = Provider

    def test_provides_value(self, provider: Provider, injector, scope):
        assert provider.bind(injector, provider.provides)(scope, provider.provides) is scope[provider.uses]
        
        