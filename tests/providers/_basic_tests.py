from types import GenericAlias
import typing as t
import inspect as ins
import pytest
from functools import wraps

from laza.di import IocContainer, Injector, InjectionToken, providers_new as providers







class BasicProviderTests:


    def test_basic(self):
        # print(f' --> Provider({ins.signature(providers.Provider)})')
        # print(f' --> Callable({ins.signature(providers.Callable)})')
        # print(f' --> Alias({ins.signature(providers.Alias)})')
        # print(f' --> {providers.Provider.__dict__=}')
        # print(f' --> {providers.Alias.__dict__=}')
        # print(f' --> {providers.Callable.__dict__=}')
        # print(f' --> {type(providers.Function.__dict__["uses"])}')

        assert 1


