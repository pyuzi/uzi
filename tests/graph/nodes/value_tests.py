import pytest
import typing as t




from uzi.graph.nodes import Value as Dependency


Dependency = Dependency
from .abc import NodeTestCase, _T_NewNode



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




_T_NewNode = _T_NewNode[Dependency]


class ValueDependencyTests(NodeTestCase[Dependency]):

    @pytest.fixture
    def concrete(self, value_setter):
        return value_setter()

    def test_validity(self, new: _T_NewNode, mock_injector):
        subject= new()
        fn = subject.bind(mock_injector)
        val = fn()
        assert val is fn() is self.value
        assert val is fn() is self.value
        