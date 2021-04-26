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

    def _test_calls(self):

        def func(a, b,*, c, d):
            return f'{a} {b} {c} {d}'

        class Obj:
            __slots__ = ()

            def __call__(self, a, b,*, c, d):
                return f'{a} {b} {c} {d}'
                
        class Attr:
            __slots__ = '__call__'

            def __init__(self):
                def __call__(a, b,*, c, d):
                    return f'{a} {b} {c} {d}'
                self.__call__ = __call__

        obj = Obj()
        attr = Attr()

        cfunc = lambda: func(1,2,c=3,d=4)
        _pfunc = partial(func, 1,2,c=3,d=4)
        pfunc = lambda: _pfunc()
        
        cobj = lambda: obj(1,2,c=3,d=4)
        _pobj = partial(obj, 1,2,c=3,d=4)
        pobj = lambda: _pobj()

        cattr = lambda: attr(1,2,c=3,d=4)
        _pattr = partial(attr, 1,2,c=3,d=4)
        pattr = lambda: _pattr()
 
        n = int(1e5)

        self.run(' func', cfunc, pfunc, n)
        self.run(' obj ', cobj, pobj, n)
        self.run(' attr', cattr, pattr, n)

        assert 0

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
                        mkfoo = lambda: Foo(user_func_symb(), user=user_func_str(), inj=null())
                        # mkfoo = lambda: Foo('a very simple value here', user=user_func_str(), inj=null())
                        mkbaz = lambda: null() or Baz() 
                        mkfunc = lambda: user_func_injectable(user_func_str(), mkfoo())
                        mkbar = lambda: Bar(mkfoo(), mkfoo(), user_func_str(), mkfunc(), sym=user_func_symb(), baz=mkbaz())
                        injfoo = lambda: injector[Foo]
                        injbar = lambda: inj[Bar]
                        injbafoo = lambda: inj[Bar].infoo
                        injbaz = lambda: inj[Baz]
                        inj404 = lambda: inj['404']

                        print(f'{injfoo()}\n {injbar()}\n')

                        _n = int(1e5)
                        self.run('Baz', mkbaz, injbaz, _n)
                        self.run('Foo', mkfoo, injfoo, _n)
                        self.run('Bar', mkbar, injbar, _n)

        assert 0
        return


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

