from contextlib import nullcontext
import os
# from django import setup

# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example_app.test_settings")

# setup()

from types import FunctionType, MethodType
import typing as t
import pickle

from timeit import repeat

import pytest




from ... import is_injectable, scope, injector



from .mocks import *

from statistics import mean, median

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




class SymbolTests:

    ops_per_sec = ops_per_sec

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

    def test_speed(self):
        # with scope('local'):
        with nullcontext():
            # with scope('local') as inj:
            with nullcontext():

            #     print('*'*16, inj,'*'*16)
            #     # with scope('abc') as _inj:
                #     nl = "\n    -- "
                with scope('abcd') as inj:
                    null = lambda: None
                    mkfoo = lambda: Foo('simple foo', user_func_str(), null())
                    mkbaz = lambda: Baz()
                    mkfunc = lambda: user_func_injectable(user_func_str())
                    mkbar = lambda: Bar(mkfoo(), mkfunc(), user_func_symb(), mkbaz())
                    injfoo = lambda: injector[Foo]
                    injbar = lambda: inj[Bar]
                    injbaz = lambda: inj[Baz]
                    inj404 = lambda: inj['404']


                    _n = int(5e4)
                    self.run('Baz', mkbaz, injbaz, _n)
                    self.run('Foo', mkfoo, injfoo, _n)
                    self.run('Bar', mkbar, injbar, _n)
                    self.run('404', mkbaz, inj404, _n)

                    print(f'Bar --->\n  {injbar()}\n  {injbar()}\n  {injbar()}\n  {injbar()!r}')
        assert 0
        return

        # print('')
        # for n, st in registry.scope_types.all_items():
        #     print(f'Scope Types: {n}', *map(repr, st), sep='\n   - ')
        
        # print('')
        # print('Scopes:')
        # for n, st in registry.scopes.items():
        #     print(f' - {n}: {st}', *st.providers, sep="\n    - ")
        
        # print('')


    def run(self, lbl, mfn, ifn, n=int(1e4), rep=7, r=3):
        mres, mt = ops_per_sec(n, *repeat(mfn, number=n, repeat=rep, globals=locals()))
        ires, it = ops_per_sec(n, *repeat(ifn, number=n, repeat=rep, globals=locals()))
        if mres > ires:
            d = f'M {round(mres/ires, r)}x faster'
        else:
            d = f'I {round(ires/mres, r)}x faster'
        M, I = f'{round(mt, r)} secs'.ljust(16) + f'{round(mres, r)} ops/sec'.ljust(16+r), \
            f'{round(it, r)} secs'.ljust(16) + f'{round(ires, r)} ops/sec'.ljust(16+r)
        print(f' >> {lbl} {rep} x {n} ops {M=!s} <=> {I=!s} --> {d}')

