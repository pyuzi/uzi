import pytest
import typing as t




from xdi._dependency import Singleton as Dependency
from xdi.injectors import Injector


Dependency = Dependency
from .abc import _T_NewDep, DependencyTestCase



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




_T_NewDep = _T_NewDep[Dependency]


class SingletonDependencyTests(DependencyTestCase[Dependency]):


    def test_validity(self, new: _T_NewDep, mock_injector: Injector):
        subject= new()
        fn = subject.bind(mock_injector)
        val = fn()
        assert val is fn() is self.value
        assert val is fn() is self.value
        
