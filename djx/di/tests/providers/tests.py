from types import FunctionType, MethodType
import typing as t
import pickle

from timeit import repeat

import pytest

from weakref import WeakMethod, ref
from ...providers import (
    provide, injectable, alias, Provider, ProviderStack, 
    FactoryProvider, ValueProvider, AliasProvider, registry, 
)

from ... import is_injectable, scope, get, injector
from djx import di



from .mocks import *

from statistics import mean, median

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




class SymbolTests:

    ops_per_sec = None

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
        self.ops_per_sec = ops_per_sec


        # with scope('abc') as _inj:
        #     nl = "\n    -- "
        with scope('abcd') as inj:

            mkfoo = lambda: Foo('simple foo', user_func_str())
            mkbaz = lambda: Baz()
            mkfunc = lambda: user_func_injectable(user_func_str())
            mkbar = lambda: Bar(mkfoo(), mkfunc(), user_func_symb(), mkbaz())
            injfoo = lambda: injector[Foo]
            injbar = lambda: inj[Bar]
            injbaz = lambda: inj[Baz]

            _n = int(2e4)                
            self.run('Baz', mkbaz, injbaz, _n)
            self.run('Foo', mkfoo, injfoo, _n)
            self.run('Bar', mkbar, injbar, _n)


        print('')
        for n, st in registry.scope_types.all_items():
            print(f'Scope Types: {n}', *map(repr, st), sep='\n   - ')
        
        print('')
        print('Scopes:')
        for n, st in registry.scopes.items():
            print(f' - {n}: {st}', *st.providers, sep="\n    - ")
        
        print('')

        assert 0

    def run(self, lbl, mfn, ifn, n=int(1e5), r=3):
        mres = self.ops_per_sec(n, *repeat(mfn, number=n))
        ires = self.ops_per_sec(n, *repeat(ifn, number=n))
        if mres > ires:
            d = f'M {round(mres/ires, r)}x faster'
        else:
            d = f'I {round(ires/mres, r)}x faster'
        M, I = f'{round(mres, r)} op/sec'.ljust(16+r), f'{round(ires, r)} op/sec'.ljust(16+r)
        print(f' >> {lbl} {M=!s} <=> {I=!s} --> {d}')
