

from copy import copy, deepcopy
from inspect import ismethod
import typing as t
import pytest


from collections import abc
from xdi.markers import ProAndPredicate, _PredicateBase, ProInvertPredicate, ProOrPredicate, ProPredicate



from .. import assertions

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


T_Pred = t.TypeVar('T_Pred', bound=_PredicateBase, covariant=True)

_T_New = abc.Callable[...,T_Pred]
T_New = type[T_Pred]


@ProPredicate.register
class TestPred: 
    ...


@pytest.fixture
def immutable_attrs(cls):
    return [a for a in dir(cls) if not (a[:2] == '__' == a[-2:] or ismethod(getattr(cls, a)))]


@pytest.fixture
def new_predicate_args():
    return ()


@pytest.fixture
def new_predicate(new_predicate_args, new):
    return lambda *a, **kw: new(*a, *new_predicate_args[len(a):], **kw)



def test_basic(new_predicate: _T_New, cls):
    sub = new_predicate()
    assert isinstance(sub, cls)
    assert isinstance(sub, ProPredicate)
    str(sub)


def test_compare(new_predicate: _T_New):
    sub1, sub2, sub3 = new_predicate(), new_predicate(), new_predicate()
    assert sub1 == sub2 == sub3
    assert not(sub1 != sub2 or sub1 != sub3 or sub2 != sub3)
    assert not sub1 > sub2
    assert not sub1 < sub2
    assert sub1 >= sub2
    assert sub1 <= sub2
    assert sub1 != object()
    assert not sub1 == object()
    

def test_copy(new_predicate: _T_New):
    sub = new_predicate()
    cp = copy(sub)
    assert sub == cp
    assert isinstance(cp, sub.__class__)
    

def test_deepcopy(new_predicate: _T_New):
    sub = new_predicate()
    cp = deepcopy(sub)
    assert sub == cp
    assert isinstance(cp, sub.__class__)
    

def test_immutable(new_predicate: _T_New, immutable_attrs):
    assertions.is_immutable(new_predicate(), immutable_attrs)



def test_simple_and(new_predicate: _T_New):
    sub1, sub2 = new_predicate(), new_predicate()
    assert sub1 == sub2 and sub1 == (sub1 & sub2)
    res = sub1 & ~sub2
    assert res != sub1 != ~sub2
    assert isinstance(res, ProAndPredicate)

def test_simple_rand(new_predicate: _T_New):
    assert isinstance(TestPred() & new_predicate(), ProAndPredicate)


def test_simple_invert(new_predicate: _T_New):
    sub = new_predicate()
    res = ~sub
    assert sub != res
    assert isinstance(res, ProInvertPredicate)


def test_simple_or(new_predicate: _T_New):
    sub1, sub2 = new_predicate(), new_predicate()
    assert sub1 == sub2 and sub1 == (sub1 | sub2)
    res = sub1 | ~sub2
    assert res != sub1 != ~sub2
    assert isinstance(res, ProOrPredicate)


def test_simple_ror(new_predicate: _T_New):
    assert isinstance(TestPred() | new_predicate(), ProOrPredicate)


@xfail(raises=TypeError, strict=True)
def test_invalid_or(new_predicate: _T_New):
    new_predicate() | {1,2,3}
    

@xfail(raises=TypeError, strict=True)
def test_invalid_and(new_predicate: _T_New):
    new_predicate() & {1,2,3}
  

@xfail(raises=TypeError, strict=True)
def test_invalid_rand(new_predicate: _T_New):
    {1,2,3} & new_predicate()
    

@xfail(raises=TypeError, strict=True)
def test_invalid_ror(new_predicate: _T_New):
    {1,2,3} | new_predicate()
    


def test_pro_entries():
    assert False