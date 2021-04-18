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

        from timeit import timeit, repeat

        with scope() as inj:
            nl = "\n    -- "
            print('---', inj.providers)
            print('--- ', inj[Foo])
            print('--- ', user_symb, '::', inj[user_symb])
            print('--- ', user_symb, '::', inj[user_symb])
            print('--- ', user_symb, '::', inj[user_symb])
            print('---')

            with scope() as inj1:
                # print('--- ', user_func_injectable, '::', inj[user_symb])

                mkfoo = lambda: Foo('simple foo', user_func_str())
                injfoo = lambda: inj[Foo]
                injbar = lambda: inj1[Bar]

                print('--- ', inj1[user_func_injectable])
                print('--- ', inj1[user_func_injectable])
                print('--- ', inj1[user_func_injectable])
                print('---')
                print('--- ', inj1[Bar])
                print('--- ', inj1[user_func_injectable])
                print('--- ', inj1[Bar])
                print('--- ', inj1[user_func_injectable])
                print('--- ', inj1[Bar])
                print('---')
                n = int(1e5)
                res = repeat(mkfoo, number=n)
                print('- MAK Foo: ', res)

                res = repeat(injbar, number=n)
                print('- INJ Bar: ', res)

                res = repeat(injfoo, number=n)
                print('- INJ Foo: ', res)

            # for s in registry.all_providers:
            #     print(f'scope: {s}')
            #     col = registry.all_providers[s]
            #     for k, v in col.all_items():
            #         print(f' - {k} --> {col[k]}', *map(str, v), sep=nl)
            #     print('')

            assert 0
        
    