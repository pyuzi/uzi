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

        assert isinstance(injector(Foo), Foo)
        assert isinstance(injector(Bar), Bar)
        assert isinstance(injector(Baz), Baz)
        assert isinstance(injector(FooBar), FooBar)
        assert isinstance(injector(FooBarBaz), FooBarBaz)
        assert isinstance(injector(Service), Service)


