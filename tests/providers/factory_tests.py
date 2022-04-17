import asyncio
import pytest

import typing as t
from xdi import Dep



from xdi.providers import Factory as Provider




from .abc import ProviderTestCase, AsyncProviderTestCase, _T_NewPro


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

_T_NewPro =  _T_NewPro[Provider]

class FactoryProviderTests(ProviderTestCase[Provider]):
    
    # @pytest.fixture
    # def provider(self, factory):
    #     return Provider(factory)

    # @pytest.fixture
    # def factory(self, value_setter):
    #     return value_setter

    # def test_singleton(self, provider: Factory):
    #     rv = provider.singleton()
    #     assert rv is provider
    #     assert provider.is_shared
    #     assert not provider.singleton(False).is_shared

    @pytest.fixture
    def concrete(self):
        def fn(a: Foo, /, b: Bar, *, z=Dep(Baz, default=None)): ...
        return fn

    def test_args_kwargs(self, new: _T_NewPro):
        subject = new()
        
        args = 1,2,3
        kwd = dict(foo=Foo, bar=Bar)

        assert subject.args(*args) is subject
        assert subject.kwargs(**kwd) is subject
        rargs, rkwds = subject.arguments

        assert rargs == args
        assert rkwds == kwd

        args = 4,5,7
        subject.args(*args)
        assert (args, kwd) == subject.arguments

        kwd = dict(foobar=122, baz=Baz)
        subject.kwargs(**kwd)
        assert (args, kwd) == subject.arguments

    def _test_with_args(self, scope, context):
        _default = object()
        
        def func(a: Foo, b: Bar, c=_default, /):
            assert (a, b, c) == args[:3]
        
        provider = Provider(func)

        args = 'aaa', 123, 'xyz'
        provider.args(*args)
        provider.resolve(scope, func).factory(context)()

        provider = Provider(func)

        args = 'aaa', 123, _default
        provider.args(*args[:-1])
        provider.resolve(scope, func).factory(context)()
        
    def _test_with_kwargs(self, scope, context):
        _default = object()
        
        def func(*, a: Foo, b: Bar, c=_default):
            assert dict(a=a, b=b, c=c) == {'c': _default } | kwargs
        
        provider = Provider(func)

        kwargs = dict(a='aaa', b=123, c='xyz')
        provider.kwargs(**kwargs)
        provider.resolve(scope, func).factory(context)()

        provider = Provider(func)

        kwargs = dict(a='BAR', b='BOO')
        provider.kwargs(**kwargs)
        provider.resolve(scope, func).factory(context)()


# class AsyncFactoryProviderTests(FactoryProviderTests, AsyncProviderTestCase):

#     @pytest.fixture
#     def scope(self, scope):
#         tval = object()
#         scope[_T] = lambda c: lambda: tval
#         afn = lambda c: lambda: asyncio.sleep(0, tval)
#         afn.is_async = True
#         scope[_T_Async] = afn
#         return scope

#     @pytest.fixture
#     def factory(self, value_setter):
#         async def factory(a: _T, b: _T_Async):
#             assert a is b
#             return await value_setter()
#         return factory

