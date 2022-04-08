from os import name
import typing as t
import pytest




from xdi.containers import Container
from xdi import Scope




xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



_T = t.TypeVar('_T')
_Ta = t.TypeVar('_Ta')
_Tb = t.TypeVar('_Tb')
_Tc = t.TypeVar('_Tc')
_Tx = t.TypeVar('_Tx')




class ContainerTestCase:

    cls: t.ClassVar[type[Container]] = Container

    @pytest.fixture
    def make(self):
        yield self.cls

    @pytest.fixture
    def scope(self, scope: Scope):
        # for t_ in (_Ta, _Tb, _Tc):
        #     scope.value(t_, f'{uniqueid[t_]()}.00-scope-{scope.name}')
        return scope


