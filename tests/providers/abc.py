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
        res = provider.provide(scope, type)
        assert callable(res)
        assert isinstance(getattr(res, 'deps', set()), Set)
        assert isinstance(res(injector), InjectorVar) or not self.strict_injectorvar
        
        
    

