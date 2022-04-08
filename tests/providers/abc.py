from inspect import isawaitable
from time import sleep
import typing as t
import pytest


from collections.abc import Set


from xdi.providers import Provider
from xdi import Scope

from xdi import InjectionMarker, is_injectable




xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



_notset = object()


class ProviderTestCase:

    cls: t.ClassVar[type[Provider]] = Provider
    strict_injectorvar = True
    value = _notset
    provider: Provider

    @property
    def provides(self):
        return self.provider.provides
    
    @pytest.fixture(autouse=True)
    def _setup_provider(self, provider):
        self.provider = provider

    @pytest.fixture
    def value_factory(self):
        return lambda: object()

    @pytest.fixture
    def value_setter(self, value_factory):
        def fn(*a, **kw):
            self.value = val = value_factory(*a, **kw)
            return val
        return fn

    def test_basic(self, provider: Provider):
        assert isinstance(provider, Provider)
        assert isinstance(provider, InjectionMarker)

    def test_set_container(self, provider: Provider, container):
        assert provider.container is None
        provider.set_container(container).set_container(container)
        assert provider.container is container

    @xfail(raises=AttributeError, strict=True)
    def test_xfail_multiple_set_container(self, provider: Provider, Container):
        assert provider.container is None
        provider.set_container(Container()).set_container(Container())

    def test_is_default(self, provider: Provider):
        provider.default()
        assert provider.is_default is True
        provider.default(False)
        assert provider.is_default is False

    def test_is_final(self, provider: Provider):
        provider.final()
        assert provider.is_final is True
        provider.final(False)
        assert provider.is_final is False

    def test__dependency__(self, provider: Provider):
        assert provider.container is None
        dep = provider.__dependency__
        assert dep is provider or is_injectable(dep)
        
    @xfail(raises=ValueError, strict=True)        
    def test_xfail__dependency__with_set_container(self, provider: Provider, container):
        assert provider.container is None
        provider.set_container(container)
        provider.__dependency__
    
    def test_freeze(self, provider: Provider):
        assert not provider._frozen
        provider._freeze()
        assert provider._frozen

    @xfail(raises=AttributeError, strict=True)
    def test_xfail_frozen(self, provider: Provider):
        provider._freeze()
        provider.default(not provider.is_default)

    def test_bind(self, provider: Provider, scope, context):
        bound = provider.bind(scope, self.provides)
        assert provider._frozen
        assert callable(bound)
        func = bound(context)
        assert callable(func)
                
    def test_no_binds_outside_own_scope(self, provider: Provider, scope: Scope, Container):
        assert provider.container is None
        container = Container()
        print(f'{scope=}')
        print(f'{container=}')
        print(f'{scope.container.get_container(container)=}')
        print(f'{container in scope=}')
        assert not container in scope
        provider.set_container(container)
        assert provider.bind(scope, self.provides) is None
    
    def test_provide(self, provider: Provider, scope, context):
        bound =  provider.bind(scope, self.provides)
        func = bound(context)
        val = func()
        assert self.value is _notset or self.value == val
        if provider.is_shared:
            assert val is func() is func() is func()

       

class AsyncProviderTestCase(ProviderTestCase):

    @pytest.fixture
    def value_factory(self):
        async def fn():
            return object()
        return fn

    @pytest.fixture
    def value_setter(self, value_factory):
        async def fn(*a, **kw):
            self.value = val = await value_factory(*a, **kw)
            return val
        return fn

    async def test_provide(self, provider: Provider, scope, context):
        bound =  provider.bind(scope, self.provides)
        func = bound(context)
        aw = func()
        assert isawaitable(aw)
        val = await aw
        assert self.value is _notset or self.value == val
        if provider.is_shared:
            assert val is await func() is await func() is await func()
