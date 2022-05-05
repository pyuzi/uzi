import asyncio
from inspect import isawaitable, signature
from unittest.mock import AsyncMock, MagicMock
import pytest
import typing as t
from xdi import Dep
from xdi._common import FrozenDict




from xdi._bindings import Callable as Dependency
from xdi._functools import BoundParams
from xdi.injectors import Injector


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




class CallableDependencyTests(BindingsTestCase[Dependency]):

    _call_args: tuple = ()
    _call_kwargs: dict = FrozenDict()

    @pytest.fixture
    def value_setter(self, mock_graph, mock_injector: Injector):
        dep_z = Dep(_Tz, default=object())
        def fn(a: _Ta, b: _Tb, /, *_a,  z=dep_z, **_kw):
            assert _a == self._call_args
            assert _kw == self._call_kwargs
            self.check_deps({ _Ta: a, _Tb: b, dep_z: z }, mock_graph, mock_injector)
            val = self.value = object()
            return val
        return fn

    def test_validity(self, new: T_NewDep, mock_injector: Injector):
        subject= new()
        a, kw = self._call_args, self._call_kwargs = (object(),), dict(kwarg=object())

        fn = subject.bind(mock_injector)()
        val = fn(*a, **kw)
        assert val is self.value
        assert not val is fn(*a, **kw) is self.value
        assert not val is fn(*a, **kw) is self.value




from xdi._bindings import AsyncCallable as Dependency

class AsyncCallableDependencyTests(BindingsTestCase[Dependency]):

    _call_args: tuple = ()
    _call_kwargs: dict = FrozenDict()

    @pytest.fixture
    def value_setter(self, mock_graph, mock_injector: Injector):
        dep_z = Dep(_Tz, default=object())
        async def fn(a: _Ta, b: _Tb, /,  *_a,  z=dep_z, **_kw):
            assert _a == self._call_args
            assert _kw == self._call_kwargs
            self.check_deps({ _Ta: a, _Tb: b, dep_z: z }, mock_graph, mock_injector)
            val = self.value = await asyncio.sleep(0, object())
            return val
        return fn

    async def test_validity(self, new: T_NewDep, mock_injector: Injector):
        subject= new()
        fn = subject.bind(mock_injector)()
        a, kw = self._call_args, self._call_kwargs = (object(),), dict(kwarg=object())
        aw = fn(*a, **kw)
        assert isawaitable(aw)
        val = await aw
        assert val is self.value
        assert not val is await fn(*a, **kw) is self.value
        assert not val is await fn(*a, **kw) is self.value



from xdi._bindings import AwaitParamsCallable as Dependency

class AwaitParamsCallableDependencyTests(BindingsTestCase[Dependency]):

    _call_args: tuple = ()
    _call_kwargs: dict = FrozenDict()

    @pytest.fixture
    def value_setter(self, mock_graph, mock_injector: t.Union[Injector, dict[t.Any, MagicMock]]):
        dep_z = Dep(_Tz, default=object())
        mock_graph[_Tb].is_async = mock_graph[_Ty].is_async = True
        def fn(a: _Ta, b: _Tb, x: _Tx, /, *_a, y: _Ty, z=dep_z, **_kw):
            assert _a == self._call_args
            assert _kw == self._call_kwargs
            self.check_deps({ _Ta: a, _Tb: b, _Tx: x, _Ty: y, dep_z: z }, mock_graph, mock_injector)
            val = self.value = object()
            return val
        return fn

    async def test_validity(self, new: T_NewDep, mock_injector: Injector):
        subject= new()
        a, kw = self._call_args, self._call_kwargs = (object(),), dict(kwarg=object())
        fn = subject.bind(mock_injector)()
        aw = fn(*a, **kw)
        assert isawaitable(aw)
        val = await aw

        assert val is self.value
        assert not val is await fn(*a, **kw) is self.value
        assert not val is await fn(*a, **kw) is self.value



from xdi._bindings import AwaitParamsAsyncCallable as Dependency

class AwaitParamsAsyncCallableDependencyTests(BindingsTestCase[Dependency]):

    _call_args: tuple = ()
    _call_kwargs: dict = FrozenDict()


    @pytest.fixture
    def value_setter(self, mock_graph, mock_injector: t.Union[Injector, dict[t.Any, MagicMock]]):
        dep_z = Dep(_Tz, default=object())
        mock_graph[_Tb].is_async = mock_graph[_Ty].is_async = True
        async def fn(a: _Ta, b: _Tb, x: _Tx, /, *_a, y: _Ty, z=dep_z, **_kw):
            assert _a == self._call_args
            assert _kw == self._call_kwargs
            self.check_deps({ _Ta: a, _Tb: b, _Tx: x, _Ty: y, dep_z: z }, mock_graph, mock_injector)
            val = self.value = await asyncio.sleep(0, object())
            return val
        return fn

    async def test_validity(self, new: T_NewDep, mock_injector: Injector):
        subject= new()
        a, kw = self._call_args, self._call_kwargs = (object(),), dict(kwarg=object())
        fn = subject.bind(mock_injector)()
        val = await fn(*a, **kw)
        assert val is self.value
        assert not val is await fn(*a, **kw) is self.value
        assert not val is await fn(*a, **kw) is self.value




@pytest.fixture
def bound(bound):
    return bound()

