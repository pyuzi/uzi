from inspect import signature
import pytest
import typing as t



from xdi.containers import Container
from xdi.injectors import Injector
from xdi.scopes import Scope


from .abc import *


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



class Tests(FunctionalTestCase):

    def test(self):
        container = Container()
        container.provide(Foo, Bar, Baz, Service)
        container.singleton(FooBar)
        container.singleton(FooBarBaz)
        container.alias(T_Foo, Foo)
        container.alias(T_Baz, Baz)

        scope = Scope(container)

        injector = Injector(scope)

        assert isinstance(injector.make(Foo), Foo)
        assert isinstance(injector.make(Bar), Bar)
        assert isinstance(injector.make(Baz), Baz)
        assert isinstance(injector.make(FooBar), FooBar)
        assert isinstance(injector.make(FooBarBaz), FooBarBaz)
        assert isinstance(injector.make(Service), Service)

        assert injector.make(entry)


