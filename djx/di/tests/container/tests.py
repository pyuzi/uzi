from types import GenericAlias
import typing as t
import inspect as ins
import pytest


from djx.di import IocContainer, Injector, abc, Scope, ioc





xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize

_T_Foo = t.TypeVar('_T_Foo', int, float)
_T_Bar = t.TypeVar('_T_Bar', str, bytes)
_T_Baz = t.TypeVar('_T_Baz', list, tuple)

class Foo(t.Generic[_T_Foo]):

    foo: _T_Foo

    def __init__(self, foo: _T_Foo, inj: Injector) -> None:
        self.foo = foo
        
class Bar(t.Generic[_T_Bar]):

    bar: _T_Bar

    def __init__(self, foo: Foo, bar: _T_Bar=None) -> None:
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




class ContainerTests:


    def test_scope_name(self):
        ioc = IocContainer('main', scope_aliases=dict(abc='local', xyz='abc')) 

        assert ioc.scope_name('main') == 'main'
        assert ioc.scope_name('abc') == 'local'
        assert ioc.scope_name('xyz') == 'local'

    def test_basic(self):


        ioc.type(Foo, Foo, args=('FooMe',))
        ioc.type(Bar, Bar)

        assert ioc.make(Injector)

        assert ioc.is_provided(Foo)
        assert ioc.is_provided(Bar)

        assert ioc.make(Foo)
        assert ioc.make(Bar)

        # assert 0, '\n'
 

            
        
    