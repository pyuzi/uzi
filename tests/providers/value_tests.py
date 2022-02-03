import pytest





from laza.di.providers import ValueProvider


from .abc import ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


@pytest.fixture
def provider():
    return ValueProvider(object())


class ValueProviderTests(ProviderTestCase):
    
    cls = ValueProvider

    def test_provides_value(self, provider: ValueProvider, injector, scope):
        assert provider.compile(injector, type)(scope).value is provider.uses
        
        
    

