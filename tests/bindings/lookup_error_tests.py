from copy import copy
from unittest.mock import MagicMock
import pytest
import typing as t

from collections.abc import Callable
from tests.abc import BaseTestCase
from uzi import InjectorLookupError


from uzi._bindings import LookupErrorBinding as Dependency, SimpleBinding
from uzi.injectors import Injector


Dependency = Dependency



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



_T = t.TypeVar("_T")
_T_Dep = t.TypeVar('_T_Dep', bound=Dependency, covariant=True)
_T_NewDep = Callable[..., _T_Dep]


class LookupErrorDependencyTests(BaseTestCase[Dependency]):

    @pytest.fixture
    def abstract(self):
        return _T

    @pytest.fixture
    def concrete(self, value_setter):
        return MagicMock(value_setter, wraps=value_setter)

    def test_basic(self, new: _T_NewDep, cls: type[_T_Dep]):
        subject = new()
        assert isinstance(subject, Dependency)
        assert subject.__class__ is cls
        assert cls.__slots__ is cls.__dict__["__slots__"]
        assert not subject
        return subject

    def test_copy(self, new: _T_NewDep):
        subject = new()
        cp = copy(subject)
        assert cp.__class__ is subject.__class__
        assert cp == subject
        return subject, cp

    def test_compare(self, new: _T_NewDep, abstract, mock_graph):
        subject, subject_2 = new(), new()
        simp = SimpleBinding(abstract, mock_graph)
        assert subject.__class__ is subject_2.__class__
        assert subject == subject_2 == abstract
        assert subject != object()
        assert subject != simp
        assert not subject == simp
        assert subject.abstract == simp.abstract
        assert not subject != subject_2 != abstract
        assert not subject == object()
        assert hash(subject) == hash(subject_2)
        return subject, subject_2

    def test_immutable(self, new: _T_NewDep, immutable_attrs):
        self.assert_immutable(new(), immutable_attrs)

    @xfail(raises=InjectorLookupError, strict=True)
    def test_bind(self, new: _T_NewDep, mock_injector: Injector):
        subject= new()
        subject.bind(mock_injector)
