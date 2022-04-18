from copy import copy, deepcopy
from collections.abc import Callable
from inspect import isawaitable
import typing as t
from unittest.mock import AsyncMock, MagicMock
import attr
import pytest
from xdi import Dep
from xdi._common import Missing


# from xdi.providers import 
from xdi._dependency import Dependency
from xdi.injectors import Injector

from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_notset = object()

_T = t.TypeVar("_T")


class FunctionalTestCase(BaseTestCase):

    value = _notset
   




T_Foo = t.TypeVar('T_Foo', bound='Foo', covariant=True)
T_Baz = t.TypeVar('T_Baz', bound='Baz', covariant=True)





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
    
    def __init__(self, foo: Foo, bar: Bar[T_Foo], baz: t.Annotated[t.Any, Dep(T_Baz)], /) -> None:
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)
        assert isinstance(baz, Baz)
        self.foo, self.bar, self.baz = foo, bar, baz
        self.deps = foo, bar, baz,
    


class Service:
    
    def __init__(self, foo: Foo, bar: Bar, baz: Baz, /, *, foobar: FooBar, foobarbaz: FooBarBaz, bar_or_baz: t.Union[Bar, Baz], baz_bar: t.Annotated[Bar, Dep(FooBarBaz).provided.deps[1::-1][0].bar]) -> None:
        self.deps = foo, bar, baz, foobar, foobarbaz, bar_or_baz, baz_bar
        print(self, *self.deps, sep='\n  - ')
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



