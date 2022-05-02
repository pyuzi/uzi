import pytest

from xdi.markers import ProNoopPredicate as Predicate



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




@pytest.fixture
def cls():
    return Predicate


from .cases import *

_T_New = T_New[Predicate]


def test_pro_entries(new_predicate: _T_New, MockContainer):
    sub, n = new_predicate(), 10
    containers = tuple(MockContainer() for _ in range(n))
    for x in range(n):
        assert containers[x:] == sub.pro_entries(containers[x:], None, None)


    