import typing as t
import pytest


from collections.abc import Set


from laza.di.providers import Provider
from laza.di.scopes import ScopeVar




xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



class ProviderTestCase:

    cls: t.ClassVar[type[Provider]] = Provider
    strict_injectorvar = True
    var_class = ScopeVar,

    def test_basic(self, provider: Provider, injector, scope):
        assert isinstance(provider, self.cls)
        hand = provider.bind(injector, provider.provides)
        assert callable(hand)
        assert callable(hand(scope, provider.provides))
        
        
    

