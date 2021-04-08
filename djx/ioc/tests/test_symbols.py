import typing as t


import pytest

from weakref import ref
from djx.ioc.symbols import Symbol

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




class Foo:
    
    @classmethod
    def cls_method(cls, arg) -> None:
        pass

    def method1(self, arg) -> None:
        pass
    
    def method2(self, arg) -> None:
        pass
    


class Bar(Foo):

    def method2(self, arg) -> None:
        ...



class WkFoo:
    
    @classmethod
    def cls_method(cls, arg) -> None:
        pass

    def method1(self, arg) -> None:
        pass
    
    def method2(self, arg) -> None:
        pass
    


class WkBar(WkFoo):

    def method2(self, arg) -> None:
            pass
        




class SymbolTests:

    @pytest.mark.parametrize(
        "o1, o2, eq",
        [
            ['foo', 'foo', True],
            ['foo', Symbol('foo'), True],
            [Symbol('foo'), Symbol('foo'), True],
            ['foo', 'bar', False],
            [Symbol('foo'), Symbol('bar'), False],

            [Foo, Foo, True],
            [Foo, Bar, False],

            [Foo.cls_method, Foo.cls_method, True],
            [Foo().cls_method, Foo.cls_method, True],
            [Foo.cls_method, Bar.cls_method, True],
            [Foo.cls_method, Bar().cls_method, True],

            [Foo.method1, Foo.method1, True],
            [Foo().method1, Foo.method1, True],
            [Foo.method1, Bar.method1, True],
            [Foo.method1, Bar().method1, True],

            [Foo.method2, Foo.method2, True],
            [Foo().method2, Foo.method2, True],
            [Foo.method2, Bar.method2, False],
            [Foo.method2, Bar().method2, False],

            [Bar.method2, Bar.method2, True],
            [Bar().method2, Bar.method2, True],
            [Bar().method2, Bar().method2, True],

        ],
    )
    def test_basic(self, o1, o2, eq):
        s1 = Symbol(o1)
        s2 = Symbol(o2)

        assert isinstance(s1, Symbol) 
        assert isinstance(s2, Symbol)
        
        assert s1._ash == o1 or isinstance(s1._ref, ref) 
        assert s2._ash == o2 or isinstance(s2._ref, ref)

        assert isinstance(o1, Symbol) or s1() is o1 or s1() is o1.__func__
        assert isinstance(o2, Symbol) or s2() is o2 or s2() is o2.__func__

        if eq:
            assert s1 is s2
        else:
            assert s1 is not s2

        assert 1, f' {s1=!r} <=> {s2=!r}'


    def test_weakrefs(self):
        pass
