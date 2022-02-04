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

    def test_basic(self, provider: Provider, injector, scope):
        assert isinstance(provider, self.cls)
        hand = provider.compile(type)
        assert callable(hand)
        assert isinstance(getattr(hand, 'deps', set()), Set)
        assert isinstance(hand(scope), ScopeVar) or not self.strict_injectorvar
        
        
    

