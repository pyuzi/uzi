from inspect import signature
import pytest
import typing as t
from xdi import Dep




from xdi._dependency import Singleton as Dependency
from xdi.injectors import Injector
from xdi._functools import BoundParams


from .abc import _T_NewDep, DependencyTestCase



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




_T_NewDep = _T_NewDep[Dependency]

_Ta = t.TypeVar('_Ta')
_Tb = t.TypeVar('_Tb')
_Tz = t.TypeVar('_Tz')


class SingletonDependencyTests(DependencyTestCase[Dependency]):

    @pytest.fixture
    def value_setter(self, mock_scope, mock_injector: Injector):
        dep_z = Dep(_Tz, default=object())
        def fn(a: _Ta, /, b: _Tb, *, z=dep_z):
            assert a is mock_injector[mock_scope[_Ta]]() is not b is not z
            assert b is mock_injector[mock_scope[_Tb]]() is not a is not z
            assert z is mock_injector[mock_scope[dep_z]]() is not a is not b
            val = self.value = object()
            return val

        return fn

    @pytest.fixture
    def new_kwargs(self, new_kwargs, value_setter, mock_scope):
        return new_kwargs | dict(params=BoundParams.bind(signature(value_setter), mock_scope))

    def test_validity(self, new: _T_NewDep, mock_injector: Injector):
        subject= new()
        fn = subject.bind(mock_injector)
        val = fn()
        assert val is fn() is self.value
        assert val is fn() is self.value
        
