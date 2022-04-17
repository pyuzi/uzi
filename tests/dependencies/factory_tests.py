from inspect import signature
from unittest.mock import MagicMock
import pytest
import typing as t
from xdi import Dep




from xdi._dependency import Factory as Dependency
from xdi._functools import BoundParams
from xdi.injectors import Injector


from .abc import DependencyTestCase, _T_NewDep



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



_T_NewDep = _T_NewDep[Dependency]



_Ta = t.TypeVar('_Ta')
_Tb = t.TypeVar('_Tb')
_Tz = t.TypeVar('_Tz')


class FactoryDependencyTests(DependencyTestCase[Dependency]):


    @pytest.fixture
    def new_kwargs(self, new_kwargs, concrete, mock_scope, mock_provider):
        def fn(a: _Ta, /, b: _Tb, *, z=Dep(_Tz, default=None)):
            return 
        return new_kwargs | dict(params=BoundParams.bind(signature(fn), mock_scope), scope=mock_scope, provider=mock_provider, concrete=concrete)

    def test_validity(self, new: _T_NewDep, mock_injector: Injector):
        subject= new()
        fn = subject.bind(mock_injector)
        val = fn()
        assert val is self.value
        assert not val is fn() is self.value
        assert not val is fn() is self.value
        