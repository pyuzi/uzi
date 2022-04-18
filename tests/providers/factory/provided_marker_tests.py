import asyncio
from unittest.mock import MagicMock
import pytest

import typing as t
from xdi import Provided



from xdi.providers import ProvidedMarkerProvider as Provider


from ..abc import _T_NewPro, ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T_NewPro =  _T_NewPro[Provider]

_Ta = t.TypeVar("_Ta")
_Tx = t.TypeVar("_Tx")

class Foo:
    a = dict(list=list(range(10)), data=dict(bee="Im a bee"))

    class bar:
        @classmethod
        def run(cls, *args, **kwargs) -> None:
            print(f"ran with({args=}, {kwargs=})")

            return Foo



class ProvidedMarkerProviderTests(ProviderTestCase[Provider]):
    
    @pytest.fixture
    def new_args(self):
        return ()

    @pytest.fixture
    def abstract(self):
        return Provided(Foo).bar.run(1, 2, 3, k1=1, k2=2).a["list"][2:-2]

    @pytest.fixture
    def mock_injector(self, mock_scope, mock_injector):
        mock_injector[mock_scope[Foo]] = MagicMock(type[Foo], wraps=Foo)
        return mock_injector

    