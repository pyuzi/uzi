import typing as t
import pytest


from collections.abc import Set


from laza.di.providers import Provider




xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




class ProviderTestCase:

    cls: t.ClassVar[type[Provider]] = Provider
    strict_injectorvar = True


    def test_basic(self, provider: Provider, injector, injectorcontext, provided):
        assert isinstance(provider, self.cls)
        bound = provider.bind(injector)
        assert callable(bound)
        func = bound(injectorcontext)
        assert callable(func)
        val = func()
        exp = provided()
        assert val == exp
        
        
    

