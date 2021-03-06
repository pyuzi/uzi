import pytest
import typing as t


from uzi.containers import Container
from uzi.scopes import Scope


from .abc import *


xfail = pytest.mark.xfail
skip = pytest.mark.skip
parametrize = pytest.mark.parametrize


class Tests(FunctionalTestCase):
    def test(self):
        container = Container()
        container.provide(Foo, Bar, Baz)
        container.factory(Service).args(12345)
        # container.singleton(FooBarBaz)
        container.alias(T_Foo, Foo)
        container.alias(T_Baz, Baz)

        container2 = Container().extend(container)
        container2.singleton(FooBar)
        container2.singleton(FooBarBaz)

        scope = Scope(container2)

        injector = scope.injector()

        assert isinstance(injector.make(Foo), Foo)
        assert isinstance(injector.make(Bar), Bar)
        assert isinstance(injector.make(Baz), Baz)
        assert isinstance(injector.make(FooBar), FooBar)
        assert isinstance(injector.make(FooBarBaz), FooBarBaz)
        assert isinstance(injector.make(Service), Service)
        assert injector.make(entry)
        assert injector.make(entry)
