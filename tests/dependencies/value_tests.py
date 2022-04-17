import pytest
import typing as t




from xdi._dependency import Value as Dependency


Dependency = Dependency
from .abc import DependencyTestCase, _T_NewDep



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




_T_NewDep = _T_NewDep[Dependency]


class ValueDependencyTests(DependencyTestCase[Dependency]):

    @pytest.fixture
    def concrete(self, value_setter):
        return value_setter()

    def test_validity(self, new: _T_NewDep, mock_injector):
        subject= new()
        fn = subject.bind(mock_injector)
        val = fn()
        assert val is fn() is self.value
        assert val is fn() is self.value
        