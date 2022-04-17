from copy import copy, deepcopy
from collections.abc import Callable
import typing as t
from unittest.mock import MagicMock
import attr
import pytest
from xdi._common import Missing


# from xdi.providers import 
from xdi._dependency import Dependency
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

    # @pytest.fixture
    # def concrete(self, value_setter):
    #     return value_setter

    @pytest.fixture
    def concrete(self, value_setter):
        return MagicMock(value_setter, wraps=value_setter)

    @pytest.fixture
    def new_args(self, abstract, new_args):
        return (abstract, *new_args)

    @pytest.fixture
    def new_kwargs(self, new_kwargs, concrete, mock_scope, mock_provider):
        return new_kwargs | dict(scope=mock_scope, provider=mock_provider, concrete=concrete)

    @pytest.fixture
    def value_factory(self):
        return lambda *a, **kw: object()

    @pytest.fixture
    def value_setter(self, value_factory):
        def fn(*a, **kw):
            self.value = val = value_factory(*a, **kw)
            return val
        return fn

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

    # def test_deepcopy(self, new: _T_NewDep):
    #     subject = new()
    #     cp = deepcopy(subject)
    #     assert cp.__class__ is subject.__class__
    #     assert cp == subject
    #     return subject, cp

    def test_compare(self, new: _T_NewDep):
        subject, subject_2 = new(), new()
        assert subject.__class__ is subject_2.__class__
        assert subject == subject_2
        assert hash(subject) == hash(subject_2)
        return subject, subject_2

    def test_not_mutable(self, new: _T_NewDep):
        subject = new()
        for atr in attr.fields(subject.__class__):
            try:
                subject.__setattr__(atr.name, getattr(subject, atr.name, None))
            except AttributeError:
                continue
            else:
                raise AssertionError(f"mutable: {atr.name!r} -> {subject}")
        return subject
        
    def test_factory(self, new: _T_NewDep, mock_injector: Injector):
        subject= new()
        fn = subject.bind(mock_injector)
        assert callable(fn)
        val = fn()
        assert val is self.value
        
        