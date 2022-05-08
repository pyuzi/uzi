import typing as t
import attr
import pytest


from collections.abc import Callable
from uzi import providers
from uzi.containers import Container
from uzi.providers import ProviderRegistry





from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize

ProviderRegistry = Container

_T_Reg = t.TypeVar('_T_Reg', bound=ProviderRegistry)

_T_FnNew = Callable[..., _T_Reg]




T_Foo = t.TypeVar('T_Foo', bound='Foo', covariant=True)
T_Bar = t.TypeVar('T_Bar', bound='Bar', covariant=True)


class Foo:
    ...

class Bar(t.Generic[T_Foo]):
    ...

   

class ProviderRegistryTests(BaseTestCase[ProviderRegistry]):

    def test_basic(self, new: _T_FnNew):
        sub = new()
        assert isinstance(sub, ProviderRegistry)

    def test_provide(self, new: _T_FnNew):
        sub = new()
        pls = [
            Foo, 
            (T_Foo, Foo()),
            (T_Bar, providers.Value(Foo())),
            providers.DepMarkerProvider(),
        ]
        sub.provide(*pls)
    
    @xfail(raises=ValueError, strict=True)
    def test_provide_fail(self, new: _T_FnNew):
        sub = new()
        sub.provide(object())
