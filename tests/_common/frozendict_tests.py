from copy import copy, deepcopy
import operator
import pickle
import pytest


from xdi._common import FrozenDict






xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




class FrozenDictTests:

    def test_basic(self):
        vals = dict(a=1, b=2, c=3)
        dct = FrozenDict(vals)
        assert isinstance(dct, FrozenDict)
        assert dct == vals == FrozenDict(**vals)
        assert { dct: vals }[FrozenDict(vals)] is vals 
        for cp in (copy(dct), deepcopy(dct)):
            assert isinstance(cp, FrozenDict) 
            assert cp == dct
      
    @xfail(raises=TypeError, strict=True)
    @parametrize(['op', 'args'], [
        (operator.setitem, ('a', 1)),
        (operator.delitem, ('a',)),
        (operator.ior, ({'a': 1},)),
        (FrozenDict.update, ({'a': 1},)),
        (FrozenDict.setdefault, ('a', 1)),
        (FrozenDict.pop, ('a',)),
        (FrozenDict.popitem, ()),
        (FrozenDict.clear, ()),
    ])
    def test_xfail_not_mutable(self, op, args):
        op(FrozenDict(a=1, b=2, c=3), *args)

    @xfail(raises=TypeError, strict=True)
    def test_xfail_not_hashable(self):
        vals = dict(a=1, b={}, c=[])
        dct = FrozenDict(vals)
        { dct: vals }[dct]

    @xfail(raises=TypeError, strict=True)
    def test_xfail_not_xhashable(self):
        vals = dict(a=1, b=2, c=3)
        dct = FrozenDict(vals)
        dct._hash = None
        { dct: vals }[dct]

    def test_or(self):
        vals = dict(a=1, b=2, c=3)
        dct = FrozenDict(a=1, d=2, e=3) | vals
        res = dct | vals
        assert isinstance(dct, FrozenDict)
        assert res == dict(a=1, b=2, c=3, d=2, e=3)

    def test_pickle(self):
        dct = FrozenDict(a=1, b=2, c=3)
        pk = pickle.loads(pickle.dumps(dct))
        assert isinstance(pk, FrozenDict)
        assert dct == pk