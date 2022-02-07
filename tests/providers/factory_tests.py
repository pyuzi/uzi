import pytest

import typing as t



from laza.di.providers import Factory
from laza.di.injectors import Injector

from memory_profiler import profile
from copy import deepcopy, copy


from .abc import ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')

@pytest.fixture
def provider():
    return Factory(lambda: 'value')




class FactoryProviderTests(ProviderTestCase):
    
    cls = Factory

    def test_provides_value(self, provider: Factory, injector, scope):
        assert provider.compile(type)(scope).get() == 'value'

    def test_singleton(self, provider: Factory):
        rv = provider.singleton()
        assert rv is provider
        assert provider.is_singleton
        assert not provider.singleton(False).is_singleton
        
    def test_depends(self, provider: Factory):
        deps = dict(foo=Foo, bar=Bar)
        rv = provider.depends(**deps)
        assert rv is provider
        assert provider.deps == deps

        deps = dict(bar='bar', baz=Baz)
        provider.depends(**deps)
        assert provider.deps == deps

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

    def _test_with_args(self, injector, scope):
        _default = object()
        
        def func(a: Foo, b: Bar, c=_default):
            assert (a, b, c) == args
        
        provider = Factory(func)

        args = 'aaa', 123
        provider.args(*args)
        provider.compile(func)(scope).get()
        
    def _test_profile(self, injector, scope):
        
        def mk():
            return Factory(Foo, FooBar) \
                .args(object(), object(), object())\
                .kwargs(a=object(), b=object(), c=object())


        @profile
        def func(n_=10000):
            rv = [mk() for _ in range(n_)]
            cp = copy(rv)

            return rv, cp

        func()



        assert 0
    
        
    



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
