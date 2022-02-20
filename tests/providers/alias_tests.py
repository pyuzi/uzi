import pytest
import time




from laza.di.providers import Alias as Provider
from laza.di.common import InjectionToken
from laza.di.injectors import Injector

from .abc import ProviderTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


token = InjectionToken('aliased') 


@pytest.fixture
def provider(injector:Injector, injectorcontext):
    injector.value(token, f'VALUE FOR [{token=!r}]!')
    return Provider(type, token)



@pytest.fixture
def provided(provider:Provider, injectorcontext):
    return injectorcontext[provider.uses]




class AliasProviderTests(ProviderTestCase):

    cls = Provider

