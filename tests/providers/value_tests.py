import pytest





from laza.di.providers import ValueProvider


from .abc import ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


@pytest.fixture
def provider(injector):
    return ValueProvider(object())


class ValueProviderTests(ProviderTestCase):
    
    cls = ValueProvider

    def test_provides_value(self, provider: ValueProvider, scope, injector):
        assert provider.provide(scope, type)(injector).value is provider.uses
        
        
    

