import pytest

from uzi.markers import ScopePredicate as Predicate
from uzi.graph.core import Graph, DepSrc


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


@pytest.fixture
def cls():
    return Predicate


from .cases import *


@pytest.fixture(params=Predicate)
def new_predicate_args(request):
    return (request.param,)


_T_New = T_New[Predicate]


def test_immutable():
    pass


@xfail(raises=ValueError, strict=True)
def test_create_invalid(new_predicate):
    new_predicate("sdfgnbfsdadfgvb")


def test_pro_entries(
    new_predicate: _T_New,
    cls: type[Predicate],
    MockDepSrc: type[DepSrc],
    MockGraph: type[Graph],
    MockContainer,
):
    sub = new_predicate()
    n = 5
    containers = tuple(MockContainer() for _ in range(n))
    if sub is cls.only_self:
        src = MockDepSrc()
        assert sub.pro_entries(containers, src.graph, src) == containers
        assert sub.pro_entries(containers, MockGraph(), src) == ()
    elif sub is cls.skip_self:
        src = MockDepSrc()
        assert sub.pro_entries(containers, src.graph, src) == ()
        assert sub.pro_entries(containers, MockGraph(), src) == containers
