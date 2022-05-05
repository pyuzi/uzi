from inspect import ismethod
import typing as t
import attr
import pytest

from unittest.mock import  Mock

from collections.abc import Callable, Iterator, Set, MutableSet, Mapping


from xdi.containers import Container
from xdi.graph import NullGraph, DepGraph


from .. import assertions

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



_T = t.TypeVar('_T')
_T_FnNew = Callable[..., DepGraph]

   

@pytest.fixture
def new_args(MockContainer: type[Container]):
    return MockContainer(),

@pytest.fixture
def cls():
    return DepGraph



@pytest.fixture
def immutable_attrs(cls):
    return [a for a in dir(cls) if not (a[:2] == '__' == a[-2:] or ismethod(getattr(cls, a)))]


