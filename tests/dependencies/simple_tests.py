from unittest.mock import MagicMock
import pytest
import typing as t

from collections.abc import Callable


from xdi._dependency import SimpleDependency as Dependency


Dependency = Dependency
from .abc import DependencyTestCase, _T_NewDep



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




_T_NewDep = _T_NewDep[Dependency]


class SimpleDependencyTests(DependencyTestCase[Dependency]):

    @pytest.fixture
    def concrete(self, value_setter):
        wrap = MagicMock(Callable, wraps=value_setter)
        return MagicMock(Callable[..., Callable], wraps=lambda i: wrap)

    def test_validity(self, new: _T_NewDep, concrete: MagicMock, mock_injector):
        subject= new()
        fn = subject.bind(mock_injector)
        val = fn()
        assert not val is fn() is self.value
        assert not val is fn() is self.value
        concrete.assert_called_with(mock_injector)
        