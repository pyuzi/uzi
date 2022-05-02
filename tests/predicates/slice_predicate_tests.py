import pytest

from xdi.markers import ProSlice as Predicate



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




@pytest.fixture
def cls():
    return Predicate


from .cases import *

_T_New = T_New[Predicate]



def test_pro_entries(new_predicate: _T_New, MockProPredicate: _T_New, MockContainer):
    pred1, pred2 = MockProPredicate(), MockProPredicate()
    n = 16
    containers = tuple(MockContainer() for _ in range(n))
    
    pred1.pro_entries.return_value = containers[n//4:]
    pred2.pro_entries.return_value = containers[-n//4:]

    sub = new_predicate(pred1, pred2)
    assert sub.pro_entries(containers, None, None) == containers[n//4:-n//4]

    sub = new_predicate(pred1)
    assert sub.pro_entries(containers, None, None) == containers[n//4:]

    sub = new_predicate(pred1, pred2, 2)
    assert sub.pro_entries(containers, None, None) == containers[n//4:-n//4:2]




    