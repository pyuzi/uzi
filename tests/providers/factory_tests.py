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


@pytest.fixture
def provided():
    return lambda: 'value'





class FactoryProviderTests(ProviderTestCase):
    
    cls = Factory

    def test_singleton(self, provider: Factory):
        rv = provider.singleton()
        assert rv is provider
        assert provider.is_singleton
        assert not provider.singleton(False).is_singleton

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

    def test_with_args(self, injector, injectorcontext):
        _default = object()
        
        def func(a: Foo, b: Bar, c=_default, /):
            assert (a, b, c) == args[:3]
        
        provider = Factory(func)

        args = 'aaa', 123, 'xyz'
        provider.args(*args)
        provider.bind(injector, func)(injectorcontext)()

        provider = Factory(func)

        args = 'aaa', 123, _default
        provider.args(*args[:-1])
        provider.bind(injector, func)(injectorcontext)()
        
    def test_with_kwargs(self, injector, injectorcontext):
        _default = object()
        
        def func(*, a: Foo, b: Bar, c=_default):
            assert dict(a=a, b=b, c=c) == {'c': _default } | kwargs
        
        provider = Factory(func)

        kwargs = dict(a='aaa', b=123, c='xyz')
        provider.kwargs(**kwargs)
        provider.bind(injector, func)(injectorcontext)()

        provider = Factory(func)

        kwargs = dict(a='BAR', b='BOO')
        provider.kwargs(**kwargs)
        provider.bind(injector, func)(injectorcontext)()
 
 
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
