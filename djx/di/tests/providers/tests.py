from contextlib import nullcontext
import os
from functools import partial, partialmethod
# from django import setup

# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example_app.test_settings")

# setup()

from types import FunctionType, MethodType
import typing as t
import pickle

from timeit import repeat

import pytest




from ... import is_injectable, scope, injector, INJECTOR_TOKEN



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

    def test_late_provider(self):
        @injectable(scope='main')
        class Early:
            

            def __str__(self) -> str:
                return ''
        
        @injectable(scope='main')
        class Late:
            pass

        with scope('test') as inj:
            with inj.context:
                key = 'late'
                val ='This was injected late'
                assert inj.get(key) is None

                provide(key, value=val)

                print('', *inj.scope.providers.maps, end='\n\n', sep='\n -')
                print('\n', *(f' - {k} --> {v!r}\n' for k,v in injector.content.items()))

                assert inj[key] == val

                assert isinstance(inj[Early], Early)
                assert not isinstance(inj[Early], Late)

                alias(Early, Late, scope='main')

                assert not isinstance(inj[Early], Early)
                assert isinstance(inj[Early], Late)
        # assert 0
                
    def test_speed(self):
        # with scope() as inj:
        with nullcontext():
            # with scope('local') as inj:
            # with inj.context:

            #     print('*'*16, inj,'*'*16)
            #     # with scope('abc') as _inj:
                #     nl = "\n    -- "
                with scope('test') as inj:
                    with inj.context:
                        null = lambda: None
                        mkinj = lambda: injector()
                        mkfoo = lambda: Foo(user_func_symb(), user=user_func_str(), inj=mkinj())
                        # mkfoo = lambda: Foo('a very simple value here', user=user_func_str(), inj=null())
                        mkbaz = lambda: null() or Baz() 
                        mkfunc = lambda: user_func_injectable(user_func_str(), mkfoo())
                        mkbar = lambda: Bar(mkfoo(), mkfoo(), user_func_str(), mkfunc(), sym=user_func_symb(), baz=mkbaz())
                        injfoo = lambda: inj[Foo]
                        injbar = lambda: inj[Bar]
                        injbafoo = lambda: inj[Bar].infoo
                        injbaz = lambda: inj[Baz]
                        inj404 = lambda: inj['404']


                        _n = int(2.5e4)
                        self.run('Baz', mkbaz, injbaz, _n)
                        self.run('Foo', mkfoo, injfoo, _n)
                        self.run('Bar', mkbar, injbar, _n)
        
                        print(f'\n => {injector[Foo]=}\n => {injector[Bar]=}\n => {injector[Bar]=}\n => {injector[Baz]=}\n => {injector[Scope["main"]]=}\n => {injector[INJECTOR_TOKEN]=}\n')

                        print('\n', *(f' - {k} --> {v!r}\n' for k,v in injector.content.items()))

                        assert injector[Bar] is not injector[Bar]


        assert 0

    def run(self, lbl, mfn, ifn, n=int(1e4), rep=3, r=3):
        mres, mt, mtt = ops_per_sec(n, *repeat(mfn, number=n, repeat=rep, globals=locals()))
        ires, it, itt = ops_per_sec(n, *repeat(ifn, number=n, repeat=rep, globals=locals()))
        if mres > ires:
            d = f'M {round(mres/ires, r)}x faster'
        else:
            d = f'I {round(ires/mres, r)}x faster'
        M, I = f'{round(mtt, r)} secs'.ljust(12) + f' avg {round(mt, r)} secs'.ljust(16) \
                    + f'{round(mres, r)} ops/sec'.ljust(16+r), \
                f'{round(itt, r)} secs'.ljust(12) + f' avg {round(it, r)} secs'.ljust(16) \
                    + f'{round(ires, r)} ops/sec'.ljust(16+r)
        print(f' - {lbl} {rep} x {n} ({rep * n}) ops == {d}\n   - {M=!s}\n   - {I=!s}')
