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
        hand = provider.compile(type)
        assert callable(hand)
        # assert isinstance(getattr(hand, 'deps', set()), Set)
        assert isinstance(hand(scope), self.var_class) or not self.strict_injectorvar
        
        
    

