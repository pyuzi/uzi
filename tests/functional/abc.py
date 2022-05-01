import typing as t
import pytest
from xdi import Dep

from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_notset = object()

_T = t.TypeVar("_T")
_Ta = t.TypeVar("_Ta")
_Tx = t.TypeVar("_Tx")
_Ty = t.TypeVar("_Ty")
_Tz = t.TypeVar("_Tz")


class FunctionalTestCase(BaseTestCase):

    value = _notset
   




T_Foo = t.TypeVar('T_Foo', bound='Foo', covariant=True)
T_Bar = t.TypeVar('T_Bar', bound='Bar', covariant=True)
T_Baz = t.TypeVar('T_Baz', bound='Baz', covariant=True)

T_FooBar = t.TypeVar('T_FooBar', bound='FooBar', covariant=True)


class Foo:
     def __init__(self) -> None:
        pass

    
class Bar(t.Generic[T_Foo]):
    
    def __init__(self, foo: T_Foo, /) -> None:
        assert isinstance(foo, Foo)
        self.foo = foo

     
class Baz:   
    
    def __init__(self, bar: Bar, /) -> None:
        assert isinstance(bar, Bar)
        self.bar = bar


 
class FooBar:
    
    def __init__(self, foo: Foo, bar: Bar, /) -> None:
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)
        self.foo, self.bar = foo, bar
        self.deps = foo, bar,



class FooBarBaz(t.Generic[T_Foo, T_Baz]):
    
    def __init__(self, foo: Foo, bar: Bar[T_Foo], baz: t.Annotated[T_Baz, Dep(T_Baz)], /) -> None:
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)
        assert isinstance(baz, Baz)
        self.foo, self.bar, self.baz = foo, bar, baz
        self.deps = foo, bar, baz,
    


class Service:
    
    def __init__(self, foo: Foo, bar: Bar, baz: Baz, /, *, foobar: FooBar, foobarbaz: FooBarBaz, bar_or_baz: t.Union[Bar, Baz], baz_bar: t.Annotated[Bar, Dep(FooBarBaz).lookup.deps[1::-1][0].bar]) -> None:
        self.deps = foo, bar, baz, foobar, foobarbaz, bar_or_baz, baz_bar
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)
        assert isinstance(baz, Baz)
        assert isinstance(foobar, FooBar)
        assert isinstance(foobarbaz, FooBarBaz)
        assert isinstance(bar_or_baz, Bar)
        assert isinstance(baz_bar, Bar)
        assert not bar is baz_bar is baz.bar
        self.foo, self.bar, self.baz, self.foobar, self.foobarbaz = foo, bar, baz, foobar, foobarbaz
        self.deps = foo, bar, baz, foobar, foobarbaz 


def entry(foo: Foo, bar: Bar, /, *args, service: Service, **kwds):
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)
        assert isinstance(service, Service)
        deps = foo, bar, args, service, kwds
        return deps

        


