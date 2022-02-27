import pytest

import typing as t



from laza.di.providers import ContextManagerProvider as Provider


from .abc import ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')







class ContextManagerProviderTests(ProviderTestCase):
    

    class ContextManager:

        def __init__(self, func):
            self.func = func
            self.enters = 0
            self.exits = 0

        def __enter__(self):
            assert self.enters == 0
            self.enters += 1
            return self.func()

        def __exit__(self, *err):
            assert self.enters == 1
            assert self.exits == 0
            self.exits += 1

    @pytest.fixture
    def provider(self, cm):
        return Provider(_T, cm)

    @pytest.fixture
    def cm(self, cm_class, value_setter):
        return cm_class(value_setter)

    @pytest.fixture
    def cm_class(self):
        return self.ContextManager

    def test_exit(self, cm: ContextManager, provider: Provider, injector, ctx_manager):
        bound = provider.bind(injector, self.provides)
        with ctx_manager as ctx:
            fn = bound(ctx)
            assert cm.enters == 0 == cm.exits
            assert fn() is fn() is fn() is fn()
            assert cm.enters == 1
            assert cm.exits == 0
        assert cm.enters == 1 == cm.exits
