import pytest
import time




from laza.di.providers import Alias, Value
from laza.di.common import InjectionToken


from .abc import ProviderTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


@pytest.fixture
def provider(injector):
    token = InjectionToken('aliased') 
    injector.add(Value(token, f'VALUE FOR [{token=!r}]!'))
    return Alias(type, token)


class AliasProviderTests(ProviderTestCase):

    cls = Alias
    

