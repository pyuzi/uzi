import pytest

import typing as t



from laza.di.providers import Value


from .abc import ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')

@pytest.fixture
def provider():
    return Value(_T, object())



class ValueProviderTests(ProviderTestCase):
    
    cls = Value

    def test_provides_value(self, provider: Value, injector, scope):
        assert provider.compile(type)(scope).value is provider.uses
        
        
    

