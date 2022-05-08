import pytest
import typing as t




from uzi._bindings import Value as Dependency


Dependency = Dependency
from .abc import BindingsTestCase, _T_NewBinding



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




_T_NewBinding = _T_NewBinding[Dependency]


class ValueDependencyTests(BindingsTestCase[Dependency]):

    @pytest.fixture
    def concrete(self, value_setter):
        return value_setter()

    def test_validity(self, new: _T_NewBinding, mock_injector):
        subject= new()
        fn = subject.bind(mock_injector)
        val = fn()
        assert val is fn() is self.value
        assert val is fn() is self.value
        