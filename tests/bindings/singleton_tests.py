import asyncio
from inspect import isawaitable, signature
from unittest.mock import MagicMock
import pytest
import typing as t
from xdi import Dep




from xdi._bindings import Singleton as Dependency
from xdi.injectors import Injector
from xdi._functools import BoundParams


from .abc import _T_NewBinding, BindingsTestCase



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




T_NewDep = _T_NewBinding[Dependency]


_Ta = t.TypeVar('_Ta')
_Tb = t.TypeVar('_Tb')
_Tc = t.TypeVar('_Tc')
_Tx = t.TypeVar('_Tx')
_Ty = t.TypeVar('_Ty')
_Tz = t.TypeVar('_Tz')

@pytest.fixture
def bound_params(value_setter, mock_graph):
    return BoundParams.bind(signature(value_setter), mock_graph)


@pytest.fixture
def new_kwargs(new_kwargs, bound_params):
    return new_kwargs | dict(params=bound_params)



class SingletonDependencyTests(BindingsTestCase[Dependency]):


    @pytest.fixture
    def value_setter(self, mock_graph, mock_injector: Injector):
        dep_z = Dep(_Tz, default=object())
        def fn(a: _Ta, /, b: _Tb, *, z=dep_z):
            self.check_deps({ _Ta: a, _Tb: b, dep_z: z }, mock_graph, mock_injector)
            val = self.value = object()
            return val

        return fn

    def test_validity(self, new: _T_NewBinding, mock_injector: Injector):
        subject= new()
        fn = subject.bind(mock_injector)
        val = fn()
        assert val is fn() is self.value
        assert val is fn() is self.value




from xdi._bindings import AsyncSingleton as Dependency

class AsyncSingletonDependencyTests(BindingsTestCase[Dependency]):


    @pytest.fixture
    def value_setter(self, mock_graph, mock_injector: Injector):
        dep_z = Dep(_Tz, default=object())
        async def fn(a: _Ta, /, b: _Tb, *, z=dep_z):
            self.check_deps({ _Ta: a, _Tb: b, dep_z: z }, mock_graph, mock_injector)
            val = self.value = await asyncio.sleep(0, object())
            return val
        return fn

    async def test_validity(self, new: T_NewDep, mock_injector: Injector):
        subject= new()
        fn = subject.bind(mock_injector)
        aw = fn()
        assert isawaitable(aw)
        val = await aw
        assert val is self.value
        assert val is await fn() is self.value
        assert val is await fn() is self.value



from xdi._bindings import AwaitParamsSingleton as Dependency

class AwaitParamsSingletonDependencyTests(BindingsTestCase[Dependency]):


    @pytest.fixture
    def value_setter(self, mock_graph, mock_injector: t.Union[Injector, dict[t.Any, MagicMock]]):
        dep_z = Dep(_Tz, default=object())
        mock_graph[_Tb].is_async = mock_graph[_Ty].is_async = True
        def fn(a: _Ta, b: _Tb, /, x: _Tx, *, y: _Ty, z=dep_z):
            self.check_deps({ _Ta: a, _Tb: b, _Tx: x, _Ty: y, dep_z: z }, mock_graph, mock_injector)
            val = self.value = object()
            return val
        return fn

    async def test_validity(self, new: T_NewDep, mock_injector: Injector):
        subject= new()
        fn = subject.bind(mock_injector)
        aw = fn()
        assert isawaitable(aw)
        val = await aw

        assert val is self.value
        assert val is await fn() is self.value
        assert val is await fn() is self.value



from xdi._bindings import AwaitParamsAsyncSingleton as Dependency

class AwaitParamsAsyncSingletonDependencyTests(BindingsTestCase[Dependency]):


    @pytest.fixture
    def value_setter(self, mock_graph, mock_injector: t.Union[Injector, dict[t.Any, MagicMock]]):
        dep_z = Dep(_Tz, default=object())
        mock_graph[_Tb].is_async = mock_graph[_Ty].is_async = True
        async def fn(a: _Ta, b: _Tb, /, x: _Tx, *, y: _Ty, z=dep_z):
            self.check_deps({ _Ta: a, _Tb: b, _Tx: x, _Ty: y, dep_z: z }, mock_graph, mock_injector)
            val = self.value = await asyncio.sleep(0, object())
            return val
        return fn

    async def test_validity(self, new: T_NewDep, mock_injector: Injector):
        subject= new()
        fn = subject.bind(mock_injector)
        val = await fn()
        assert val is self.value
        assert val is await fn() is self.value
        assert val is await fn() is self.value
