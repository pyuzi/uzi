import pytest


from uzi._common import FrozenDict, ReadonlyDict






xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




class FrozenDictTests:

    def test_basic(self):
        vals = dict(a=1, b=2, c=3)
        dct = FrozenDict(vals)
        assert isinstance(dct, FrozenDict)
        assert isinstance(dct, ReadonlyDict)
        assert dct == vals == FrozenDict(**vals)
        assert { dct: vals }[FrozenDict(vals)] is vals 
     
    @xfail(raises=TypeError, strict=True)
    def test_xfail_not_hashable(self):
        vals = dict(a=1, b={}, c=[])
        dct = FrozenDict(vals)
        { dct: vals }[dct]

