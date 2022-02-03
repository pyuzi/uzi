import pytest
import time




from laza.di.providers import AliasProvider, ValueProvider
from laza.di.common import InjectionToken


from .abc import ProviderTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


@pytest.fixture
def provider(injector):
    token = InjectionToken('aliased') 
    injector[token] = ValueProvider(f'VALUE FOR [{token=!r}]!')
    return AliasProvider(token)


class AliasProviderTests(ProviderTestCase):

    cls = AliasProvider
    

