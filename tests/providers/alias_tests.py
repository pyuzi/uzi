import pytest
import time




from laza.di.providers import AliasProvider
from laza.di.common import InjectorVar, InjectionToken


from .abc import ProviderTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


@pytest.fixture
def provider(injector):
    token = InjectionToken('aliased') 
    injector.vars[token] = InjectorVar(make=time.time)
    return AliasProvider(token)


class AliasProviderTests(ProviderTestCase):

    cls = AliasProvider
    

