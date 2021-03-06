from copy import copy, deepcopy
import typing as t
import pytest


from collections import abc


from uzi.markers import (
    Dep,
    ProNoopPredicate,
)


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar("_T")
_Tx = t.TypeVar("_Tx")

_T_FnNew = abc.Callable[..., Dep]


@pytest.fixture
def new_args():
    return (
        _T,
        ~ProNoopPredicate(),
    )


@pytest.fixture
def cls():
    return Dep


def test_basic(new: _T_FnNew):
    sub = new()
    str(sub)
    assert sub is new(sub, ProNoopPredicate())
    assert isinstance(sub, Dep)
    assert sub.abstract is _T
    assert sub == new()
    assert sub != new(_Tx)
    assert sub != _T
    assert not sub == _T
    hash(sub)
    cp = copy(sub)
    assert sub == cp == deepcopy(sub)


# def test_predicate_operations(new: _T_FnNew):
#     sub, pred = new(), ~ProNoopPredicate()
#     assert sub
#     assert isinstance((sub & pred).predicate, ProAndPredicate)
#     assert isinstance((sub | pred).predicate, ProOrPredicate)

#     assert isinstance((pred & sub).predicate, ProAndPredicate)
#     assert isinstance((pred | sub).predicate, ProOrPredicate)

# assert isinstance((~sub).predicate, ProInvertPredicate)


# @xfail(raises=TypeError, strict=True)
# @parametrize(['op', 'rev'], [(operator.or_, False), (operator.or_, True), (operator.and_, False), (operator.and_, True)])
# def test_invalid_operations(new: _T_FnNew, op, rev):
#     if rev:
#         op(object(), new())
#     else:
#         op(new(),  object())
