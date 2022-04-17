import pytest
import typing as t




from xdi._dependency import Factory as Dependency
from xdi.injectors import Injector


Dependency = Dependency
from .abc import DependencyTestCase, _T_NewDep



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




_T_NewDep = _T_NewDep[Dependency]


class FactoryDependencyTests(DependencyTestCase[Dependency]):

    @pytest.fixture
    def concrete(self, value_setter):
        return value_setter

    def test_validity(self, new: _T_NewDep, mock_injector: Injector):
        subject= new()
        fn = subject.factory(mock_injector)
        val = fn()
        assert val is self.value
        assert not val is fn() is self.value
        assert not val is fn() is self.value
        