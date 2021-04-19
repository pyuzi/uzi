from types import FunctionType, MethodType
import typing as t
import pickle


import pytest

from weakref import WeakMethod, ref
from ...symbols import (
    StaticIndentity, KindOfSymbol, SupportsIndentity, 
    UnsupportedTypeError, HashIdentity,
    symbol
)


from .mocks import *


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



class HashIdentityTests:
    """ReferredIdentityTests Object"""

    @xfail(raises=ValueError)
    def test_pickle(self):
        obj = HashIdentity(type(Foo), id(Foo))
        pickle.dumps(obj)







class SymbolTests:


    def run_basic(self, obj, kind=None):
        s = symbol(obj)

        assert isinstance(s, symbol)
        
        kind = kind or s.kind
        assert s.kind is kind
        
        assert s is symbol(s) is symbol(s()) is symbol(s.ident) is symbol(obj)

        if isinstance(obj, (symbol, ref)):
            obj = getattr(o := obj(), '__func__', o)
            assert s() is obj
        elif isinstance(obj, MethodType):
            obj = obj.__func__

        if s.kind is KindOfSymbol.LITERAL:
            assert isinstance(obj, StaticIndentity)
            assert s() is s.ident is obj
        else:
            assert isinstance(obj, SupportsIndentity)
            assert obj is s()
            # assert type(obj) is s.ident.type
            # assert id(obj) == s.ident.id

        return True

    @parametrize('obj', [
        'abc', 
        b'abc', 
        123,
        123.345,
        (1,2,3),
        frozenset((1,2,3,4,5)),
        symbol('foo'),
        symbol(12345),
        UserStaticIdentity('abc'),
        symbol(UserStaticIdentity('Foo')),
    ])
    def test_literal(self, obj) -> None:
        assert self.run_basic(obj, KindOfSymbol.LITERAL)

    @parametrize('obj', [
        Foo, 
        Bar,
        symbol,
    ])
    def test_for_class(self, obj):
        assert self.run_basic(obj, KindOfSymbol.TYPE)
    
    @parametrize('obj', [
        Foo.method1, 
        Foo.cls_method,
        Bar().method2, 
        Bar().cls_method,
        symbol(Foo.cls_method),
        symbol(Foo().method1),
        symbol(Foo.method2),
    ])
    def test_for_methods(self, obj):
        assert self.run_basic(obj, KindOfSymbol.METHOD)
       
    @parametrize('obj', [
        user_func,
        symbol(user_func),
    ])
    def test_for_functions(self, obj):
        assert self.run_basic(obj, KindOfSymbol.FUNCTION)
             
    @parametrize('obj', [
        UserIdentitySupport(1),
        symbol(supported_obj),
    ])
    def test_for_objects(self, obj):
        assert self.run_basic(obj, KindOfSymbol.OBJECT)
        
    @parametrize('obj', [
        ref(Foo),
        WeakMethod(Foo.cls_method),
    ])
    def test_for_weakrefs(self, obj):
        assert self.run_basic(obj)

    @xfail(raises=UnsupportedTypeError)    
    @parametrize('obj', [
        None,
        Foo(),
    ])
    def test_invalid(self, obj):
        self.run_basic(obj)
    
    @parametrize(
        "o1, o2, eq",
        [
            ['foo', 'foo', True],
            ['foo', symbol('foo'), True],
            [symbol('foo'), symbol('foo'), True],
            ['foo', 'bar', False],
            [symbol('foo'), symbol('bar'), False],

            [123, 123, True],
            [123, 1234, False],
            [123, '123', False],
            [(123, 123), (123, 123), True],

            [Foo, Foo, True],
            [Foo, Bar, False],

            [Foo().cls_method, Foo.cls_method, True],
            [Foo.cls_method, Bar.cls_method, True],
            [Foo.cls_method, Bar().cls_method, True],

            [Foo().method1, Foo.method1, True],
            [Foo.method1, Bar.method1, True],
            [Foo.method1, Bar().method1, True],

            [Foo.method2, Bar.method2, False],
            [Foo.method2, Bar().method2, False],

            [Bar().method2, Bar.method2, True],
            [Bar().method2, Bar().method2, True],
        ],
    )
    def test_equality(self, o1, o2, eq):
        s1 = symbol(o1)
        s2 = symbol(o2)

        if eq:
            assert s1 is s2
        else:
            assert s1 is not s2


        assert 1, f' {s1=!r} <=> {s2=!r}'

