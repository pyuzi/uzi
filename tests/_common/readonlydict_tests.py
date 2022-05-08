from copy import copy, deepcopy
import operator
import pickle
import pytest


from uzi._common import ReadonlyDict






xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




class ReadonlyDictTests:

    def test_basic(self):
        vals = dict(a=1, b=2, c=3)
        dct = ReadonlyDict(vals)
        assert isinstance(dct, ReadonlyDict)
        assert dct == vals == ReadonlyDict(**vals)
        for cp in (copy(dct), deepcopy(dct)):
            assert isinstance(cp, ReadonlyDict) 
            assert cp == dct
      
    @xfail(raises=TypeError, strict=True)
    @parametrize(['op', 'args'], [
        (operator.setitem, ('a', 1)),
        (operator.delitem, ('a',)),
        (operator.ior, ({'a': 1},)),
        (ReadonlyDict.update, ({'a': 1},)),
        (ReadonlyDict.setdefault, ('a', 1)),
        (ReadonlyDict.pop, ('a',)),
        (ReadonlyDict.popitem, ()),
        (ReadonlyDict.clear, ()),
    ])
    def test_xfail_not_mutable(self, op, args):
        op(ReadonlyDict(a=1, b=2, c=3), *args)

    def test_or(self):
        vals = dict(a=1, b=2, c=3)
        dct = ReadonlyDict(a=1, d=2, e=3) | vals
        res = dct | vals
        assert isinstance(dct, ReadonlyDict)
        assert res == dict(a=1, b=2, c=3, d=2, e=3)

    def test_pickle(self):
        dct = ReadonlyDict(a=1, b=2, c=3)
        pk = pickle.loads(pickle.dumps(dct))
        assert isinstance(pk, ReadonlyDict)
        assert dct == pk