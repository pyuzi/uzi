import asyncio
import pytest

import typing as t



from xdi.providers import Factory



from .abc import ProviderTestCase, AsyncProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_T_Async = t.TypeVar('_T_Async')


class Foo:
    def __init__(self) -> None:
        pass


class Bar:
    def __init__(self) -> None:
        pass


class Baz:
    def __init__(self) -> None:
        pass


class FooBar:
    def __init__(self) -> None:
        pass



class FactoryProviderTests(ProviderTestCase):
    
    @pytest.fixture
    def provider(self, factory):
        return Factory(factory)

    @pytest.fixture
    def factory(self, value_setter):
        return value_setter

    # def test_singleton(self, provider: Factory):
    #     rv = provider.singleton()
    #     assert rv is provider
    #     assert provider.is_shared
    #     assert not provider.singleton(False).is_shared

    def test_args_kwargs(self, provider: Factory):
        args = 1,2,3
        kwd = dict(foo=Foo, bar=Bar)

        assert provider.args(*args) is provider
        assert provider.kwargs(**kwd) is provider

        assert provider.arguments.args == args
        assert provider.arguments.kwargs == kwd

        args = 4,5,7
        provider.args(*args)

        assert provider.arguments.args == args
        assert provider.arguments.kwargs == kwd

        kwd = dict(foobar=122, baz=Baz)
        provider.kwargs(**kwd)

        assert provider.arguments.args == args
        assert provider.arguments.kwargs == kwd

    def test_with_args(self, scope, context):
        _default = object()
        
        def func(a: Foo, b: Bar, c=_default, /):
            assert (a, b, c) == args[:3]
        
        provider = Factory(func)

        args = 'aaa', 123, 'xyz'
        provider.args(*args)
        provider.bind(scope, func)(context)()

        provider = Factory(func)

        args = 'aaa', 123, _default
        provider.args(*args[:-1])
        provider.bind(scope, func)(context)()
        
    def test_with_kwargs(self, scope, context):
        _default = object()
        
        def func(*, a: Foo, b: Bar, c=_default):
            assert dict(a=a, b=b, c=c) == {'c': _default } | kwargs
        
        provider = Factory(func)

        kwargs = dict(a='aaa', b=123, c='xyz')
        provider.kwargs(**kwargs)
        provider.bind(scope, func)(context)()

        provider = Factory(func)

        kwargs = dict(a='BAR', b='BOO')
        provider.kwargs(**kwargs)
        provider.bind(scope, func)(context)()


class AsyncFactoryProviderTests(FactoryProviderTests, AsyncProviderTestCase):

    @pytest.fixture
    def factory(self, value_setter):
        async def factory(a: _T, b: _T_Async):
            assert a is b
            return value_setter()
        return factory

    @pytest.fixture
    def scope(self, scope):
        tval = object()
        scope[_T] = lambda c: lambda: tval
        scope[_T_Async] = afn = lambda c: lambda: asyncio.sleep(0, tval)
        afn.is_async = True
        return scope

