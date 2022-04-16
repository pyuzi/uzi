import pytest
import typing as t




from xdi._dependency import Singleton as Dependency


Dependency = Dependency
from .abc import DependencyTestCase, _T_NewDep



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




_T_NewDep = _T_NewDep[Dependency]


class SingletonDependencyTests(DependencyTestCase[Dependency]):

    @pytest.fixture
    def concrete(self, value_setter):
        return value_setter

