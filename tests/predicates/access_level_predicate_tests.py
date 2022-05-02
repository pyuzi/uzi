import random
from unittest.mock import MagicMock
import pytest

from xdi.markers import AccessLevel as Predicate



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




@pytest.fixture
def cls():
    return Predicate


from .cases import *


@pytest.fixture(params=[None, *Predicate])
def new_predicate_args(request):
    return (request.param,)


_T_New = T_New[Predicate]



def test_immutable():
    pass

@xfail(raises=ValueError, strict=True)
def test_create_invalid(new_predicate):
    new_predicate('sdfgnbfsdadfgvb')



def test_pro_entries(new_predicate: _T_New, cls: type[Predicate], MockDepSrc, MockContainer):
    sub = new_predicate()
    members = [*cls] * 4
    random.shuffle(members)

    n = len(members)
    x = -1
    def fn_access_level(c):
        nonlocal x
        x += 1
        return members[x]

    containers = tuple(MockContainer(access_level=MagicMock(wraps=fn_access_level)) for _ in range(n))
    res = tuple(containers[i] for i in range(n) if members[i]._rawvalue_ >= sub._rawvalue_)
    assert sub.pro_entries(containers, None, MockDepSrc()) == res

