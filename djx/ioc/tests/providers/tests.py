from types import FunctionType, MethodType
import typing as t
import pickle


import pytest

from weakref import WeakMethod, ref
from ...providers import (
    provide, injectable, alias, Provider, ProviderStack, 
    FactoryProvider, ValueProvider, AliasProvider, registry, 
)

from ... import is_injectable, scope




from .mocks import *

from statistics import mean, median

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




class SymbolTests:


    def run_basic(self, obj, kind=None):
        return True

    def test_basic(self):
        assert is_injectable(Foo)

        assert is_injectable(user_func_injectable)
        assert is_injectable(user_symb)
        assert is_injectable(user_symb())
        assert is_injectable(user_str)
        assert is_injectable(symbol(user_str))
        assert not is_injectable(noop_symb)
        assert not is_injectable(user_func_symb)

    def test_speed(self, ops_per_sec):
       
        from timeit import timeit, repeat

        with scope() as _inj:
            nl = "\n    -- "
            with scope('abc') as inj:

                mkfoo = lambda: Foo('simple foo', user_func_str())
                mkbaz = lambda: Baz()
                mkfunc = lambda: user_func_injectable(user_func_str())
                mkbar = lambda: Bar(mkfoo(), mkfunc(), user_func_symb(), mkbaz())
                injfoo = lambda: inj[Foo]
                injbar = lambda: inj[Bar]
                injbaz = lambda: _inj[Baz]
                xinjbar = lambda: _inj[Bar]

                _n = int(1e4)
                def run(lbl, mfn, ifn, n=_n, r=4):
                    mres = ops_per_sec(n, *repeat(mfn, number=n))
                    ires = ops_per_sec(n, *repeat(ifn, number=n))
                    if mres > ires:
                        d = f'M {round(mres/ires, r)}x faster'
                    else:
                        d = f'I {round(ires/mres, r)}x faster'
                    M, I = round(mres, r), round(ires, r)
                    print(f'{lbl} {M=} ops/sec, {I=} ops/sec, {d}')

                run('Foo', mkfoo, injfoo)
                run('Baz', mkbaz, injbaz)
                run('Bar', mkbar, injbar)

                print(registry.scopes)

                run('Bar', mkbar, xinjbar)


            assert 0
        

