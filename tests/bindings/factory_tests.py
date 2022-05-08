import asyncio
from inspect import isawaitable, signature
from unittest.mock import AsyncMock, MagicMock
import pytest
import typing as t
from uzi import Dep




from uzi._bindings import Factory as Dependency
from uzi._functools import BoundParams
from uzi.injectors import Injector


from .abc import BindingsTestCase, _T_NewBinding



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T_Dep = t.TypeVar('_T_Dep', bound=Dependency, covariant=True)

T_NewDep = _T_NewBinding[_T_Dep]



_Ta = t.TypeVar('_Ta')
_Tb = t.TypeVar('_Tb')
_Tc = t.TypeVar('_Tc')
_Tx = t.TypeVar('_Tx')
_Ty = t.TypeVar('_Ty')
_Tz = t.TypeVar('_Tz')


# @pytest.fixture
# def value_factory_spec(mock_graph, mock_injector: Injector):
#     dep_z = Dep(_Tz, default=object())
#     def fn(a: _Ta, /, b: _Tb, *, z=dep_z):
#         assert a is mock_injector[mock_graph[_Ta]]() is not b is not z
#         assert b is mock_injector[mock_graph[_Tb]]() is not a is not z
#         assert z is mock_injector[mock_graph[dep_z]]() is not a is not b
#         return object()
#     return fn


@pytest.fixture
def bound_params(value_setter, mock_graph):
    return BoundParams.bind(signature(value_setter), mock_graph)


@pytest.fixture
def new_kwargs(new_kwargs, bound_params):
    return new_kwargs | dict(params=bound_params)





class FactoryDependencyTests(BindingsTestCase[Dependency]):


    @pytest.fixture
    def value_setter(self, mock_graph, mock_injector: Injector):
        dep_z = Dep(_Tz, default=object())
        def fn(a: _Ta, /, b: _Tb, *, z=dep_z):
            self.check_deps({ _Ta: a, _Tb: b, dep_z: z }, mock_graph, mock_injector)
            val = self.value = object()
            return val
        return fn

    def test_validity(self, new: T_NewDep, mock_injector: Injector):
        subject= new()
        fn = subject.bind(mock_injector)
        val = fn()
        assert val is self.value
        assert not val is fn() is self.value
        assert not val is fn() is self.value




from uzi._bindings import AsyncFactory as Dependency

class AsyncFactoryDependencyTests(BindingsTestCase[Dependency]):

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
        assert not val is await fn() is self.value
        assert not val is await fn() is self.value



from uzi._bindings import AwaitParamsFactory as Dependency

class AwaitParamsFactoryDependencyTests(BindingsTestCase[Dependency]):


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
        assert not val is await fn() is self.value
        assert not val is await fn() is self.value



from uzi._bindings import AwaitParamsAsyncFactory as Dependency

class AwaitParamsAsyncFactoryDependencyTests(BindingsTestCase[Dependency]):


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
        assert not val is await fn() is self.value
        assert not val is await fn() is self.value
