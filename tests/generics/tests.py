from types import GenericAlias
import typing as t
import inspect as ins
import pytest


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize

_T_Foo = t.TypeVar('_T_Foo', int, float)
_T_Bar = t.TypeVar('_T_Bar', str, bytes)
_T_Baz = t.TypeVar('_T_Baz', list, tuple)

class Foo(t.Generic[_T_Foo]):

    foo: _T_Foo

    def __init__(self, foo: _T_Foo) -> None:
        self.foo = foo
        
class Bar(t.Generic[_T_Bar]):

    bar: _T_Bar

    def __init__(self, bar: _T_Bar) -> None:
        self.bar = bar


class FooBar(Foo[_T_Foo], Bar[_T_Bar]):

    def __init__(self, foo: _T_Foo, bar: _T_Bar) -> None:
        self.foo = foo
        self.bar = bar


class IntFoo(Foo[int]):
    ...



class FooBarBaz(Foo[float], Bar[str], t.Generic[_T_Baz]):

    def __init__(self, foo: float, bar: str, baz: _T_Baz) -> None:
        self.foo = foo
        self.bar = bar
        self.baz = baz


        


class BasicGenericTests:

    def test_basic(self):
        

        # for t in (Foo, Bar, FooBar, IntFoo, FooBarBaz, FooBar[int, _T_Bar]):
        #     if isinstance(t, GenericAlias):
        #         vardump(
        #             t, 
        #             t.__origin__, 
        #             t.__args__, 
        #             t.__parameters__, 
        #             getattr(t, '__annotations__', None),
        #             t.__init__.__annotations__,
        #         )
        #     else:
        #         vardump(
        #             t, 
        #             getattr(t, '__orig_bases__', None),
        #             t.__parameters__, 
        #             getattr(t, '__annotations__', None),
        #             t.__init__.__annotations__,
        #         )



        assert 1, '\n'
 


            
        
    