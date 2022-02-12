import pytest

import typing as t



from laza.di.providers import UnionProvider as Provider
 

from .abc import ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')

@pytest.fixture
def provider():
    return Provider(_T, object())



class UnionProviderTests__(ProviderTestCase):
    
    cls = Provider

    def test_provides_value(self, provider: Provider, injector, scope):
        assert provider.bind(injector, type)(scope)() is provider.uses
        
        
    

