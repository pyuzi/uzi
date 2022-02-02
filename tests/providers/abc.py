import typing as t
import pytest


from collections.abc import Set


from laza.di.providers import Provider
from laza.di.common import InjectorVar



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



class ProviderTestCase:

    cls: t.ClassVar[type[Provider]] = Provider
    strict_injectorvar = True

    def test_basic(self, provider: Provider, scope, injector):
        assert isinstance(provider, self.cls)
        hand = provider._handler(scope, type)
        assert callable(hand)
        assert isinstance(getattr(hand, 'deps', set()), Set)
        assert isinstance(hand(injector), InjectorVar) or not self.strict_injectorvar
        
        
    

