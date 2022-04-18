from copy import copy, deepcopy
from collections.abc import Callable
from inspect import isawaitable, ismethod
import typing as t
from unittest.mock import AsyncMock, MagicMock
import attr
import pytest
from xdi._common import Missing


# from xdi.providers import 
from xdi._dependency import Dependency, SimpleDependency
from xdi.injectors import Injector

from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_notset = object()

_T = t.TypeVar("_T")
_T_Dep = t.TypeVar("_T_Dep", bound=Dependency, covariant=True)
_T_NewDep = Callable[..., _T_Dep]


class DependencyTestCase(BaseTestCase[_T_Dep]):

    type_: t.ClassVar[type[_T_Dep]] = Dependency

    value = _notset
    
    @pytest.fixture
    def abstract(self):
        return _T

    @pytest.fixture
    def concrete(self, value_setter):
        return MagicMock(value_setter, wraps=value_setter)

    @pytest.fixture
    def subject(self, new: _T_NewDep):
        return new()

    @pytest.fixture
    def bound(self, subject: _T_Dep, mock_injector: Injector):
        return subject.bind(mock_injector)

    def check_deps(self, deps: dict, mock_scope, mock_injector: t.Union[Injector, dict[t.Any, AsyncMock]]):
        for _t, _v in deps.items():
            d = mock_scope[_t]
            _x = mock_injector[d]
            _x.assert_called()
            if getattr(d, 'is_async', False):
               _x.assert_awaited()
            assert all(_ is _t or not deps[_] is _v for _ in deps)

    def test_basic(self, new: _T_NewDep, cls: type[_T_Dep]):
        subject = new()
        assert isinstance(subject, Dependency)
        assert subject.__class__ is cls
        assert cls.__slots__ is cls.__dict__["__slots__"]
        assert subject.is_async in (True, False)
        assert callable(subject.bind)
        return subject


    def test_copy(self, new: _T_NewDep):
        subject = new()
        cp = copy(subject)
        assert cp.__class__ is subject.__class__
        assert cp == subject
        return subject, cp

    def test_compare(self, new: _T_NewDep, abstract, mock_scope):
        subject, subject_2 = new(), new()
        mock = mock_scope[abstract]
        assert subject.__class__ is subject_2.__class__
        assert subject == subject_2
        assert subject != mock
        assert subject != object()
        assert not subject == mock
        assert not subject != subject_2
        assert not subject == object()
        assert hash(subject) == hash(subject_2)
        return subject, subject_2

    def test_immutable(self, new: _T_NewDep, immutable_attrs):
        self.assert_immutable(new(), immutable_attrs)

    async def test_bind(self, subject: _T_Dep, bound):
        assert callable(bound)
        val = bound()
        if subject.is_async and isawaitable(val):
            val = await val
        if not self.value is _notset:
            assert val is self.value
        
    def test_validity(self):
        assert False, "No validity tests"