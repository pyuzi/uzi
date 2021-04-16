from types import FunctionType, MethodType
import typing as t
import pickle


import pytest

from weakref import WeakMethod, ref
from ...providers import (
    provide, injectable, alias, Provider, ProviderStack, 
    FactoryProvider, ValueProvider, AliasProvider
)

from ... import registry, is_injectable




from .mocks import *


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




class SymbolTests:


    def run_basic(self, obj, kind=None):
        return True

    def test_basic(self):
        assert is_injectable(Foo)
        assert not is_injectable(Bar)

        assert is_injectable(user_func_injectable)
        assert is_injectable(user_symb)
        assert is_injectable(user_symb())
        assert is_injectable(user_str)
        assert is_injectable(symbol(user_str))
        assert not is_injectable(noop_symb)
        assert not is_injectable(user_func_symb)

        from pprint import pp
        pp(registry.providers)
    
        assert 0
    
    