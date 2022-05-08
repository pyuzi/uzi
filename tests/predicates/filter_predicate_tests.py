import inspect
import os
from unittest.mock import MagicMock, Mock
import pytest

from uzi.markers import ProFilter as Predicate



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




@pytest.fixture
def cls():
    return Predicate


from .cases import *

_T_New = T_New[Predicate]


@pytest.fixture
def new_predicate_args():
    return MagicMock(abc.Callable),



@xfail(raises=TypeError, strict=True)
def test_non_callable(new_predicate: _T_New, MockContainer):
    sub = new_predicate(object())


def test_pro_entries(new_predicate: _T_New, MockContainer):
    n = 16
    containers = tuple(MockContainer() for _ in range(n))
    sub = new_predicate(lambda c: c in containers[n//4:-n//4])
    sub.pro_entries(containers, None, None) == containers[n//4:-n//4]
    
    
    