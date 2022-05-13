import typing as t
from unittest.mock import Mock

import pytest
from uzi.markers import Dep
from uzi.providers import DepMarkerProvider as Provider
from uzi.graph import Graph

from .abc import ProviderTestCase, _T_NewPro

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_Ta = t.TypeVar("_Ta")
_Tx = t.TypeVar("_Tx")

_T_NewPro = _T_NewPro[Provider]


class CaseConf:
    injects: t.Any
    default: t.Any
    inject_default: t.Union[t.Any, None]





class DepMarkerTests(ProviderTestCase[Provider]):


    expected: dict[Dep, CaseConf] = [
        Dep(_Tx),
        Dep(_Tx, default='[DEFAULT]'),
        Dep(_Tx, default=Dep(_Ta)),
        # Dep(_Tx, graph=Dep.ONLY_SELF, default='[DEFAULT]'),
        # Dep(_Tx, graph=Dep.ONLY_SELF, default=Dep(_Ta)),
        # Dep(_Tx, graph=Dep.SKIP_SELF),
        # Dep(_Tx, graph=Dep.SKIP_SELF, default='[DEFAULT]'),
        # Dep(_Tx, graph=Dep.SKIP_SELF, default=Dep(_Ta)),
    ]

    @pytest.fixture(params=expected)
    def abstract(self, request):
        return request.param

    @pytest.fixture
    def new_args(self):
        return ()





class Foo:
    a = dict(list=list(range(10)), data=dict(bee="Im a bee"))

    class bar:
        @classmethod
        def run(cls, *args, **kwargs) -> None:
            print(f"ran with({args=}, {kwargs=})")
            return Foo
