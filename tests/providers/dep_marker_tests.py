import typing as t

import pytest
from xdi import Dep
from xdi.providers import DepMarkerProvider as Provider

from .abc import ProviderTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_Ta = t.TypeVar("_Ta")
_Tx = t.TypeVar("_Tx")


class DepMarkerTests(ProviderTestCase):
    @pytest.fixture
    def provider(self, marker):
        return Provider(marker)

    @pytest.fixture
    def marker(self):
        return Dep(_Tx, default=Dep(_Ta))

    @pytest.fixture
    def scope(self, scope, value_setter):
        scope[_Ta] = lambda inj: value_setter
        return scope


class DepMarkerDataPathTests(DepMarkerTests):
    @pytest.fixture
    def marker(self):
        return Dep(_Ta).bar.run(1, 2, 3, k1=1, k2=2).a["list"][2:-2]

    @pytest.fixture
    def value_factory(self):
        return Foo

    @pytest.fixture
    def value_setter(self, value_factory, marker: Dep):
        def fn(*a, **kw):
            val = value_factory(*a, **kw)
            self.value = marker.__eval__(val)
            return val

        return fn


class DepMarkerOnlySelfTests(DepMarkerTests):
    @pytest.fixture
    def marker(self):
        return Dep(_Tx, injector=Dep.ONLY_SELF, default=Dep(_Ta))

    @pytest.fixture
    def scope(self, scope, Scope, Container, value_setter):
        scope = Scope(Container(), scope)
        scope[_Ta] = lambda inj: value_setter
        scope.parent[_Tx] = lambda inj: lambda: (value_setter(), object())
        return scope



class DepMarkerSkipSelfTests(DepMarkerTests):
    @pytest.fixture
    def marker(self):
        return Dep(_Tx, injector=Dep.SKIP_SELF)

    @pytest.fixture
    def scope(self, scope, Scope, Container, value_setter):
        scope = Scope(Container(), parent=scope)
        scope.parent[_Tx] = lambda inj: value_setter
        scope[_Tx] = lambda inj: lambda: (value_setter(), object())
        return scope


class Foo:
    a = dict(list=list(range(10)), data=dict(bee="Im a bee"))

    class bar:
        @classmethod
        def run(cls, *args, **kwargs) -> None:
            print(f"ran with({args=}, {kwargs=})")
            return Foo
