import typing as t
import pytest

from collections import ChainMap
from ...collections import fallbackdict, fallback_chain_dict

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



class FallbackDictTests:

    def test_basic(self):
        

        assert 1, '\n'
 


class FallbackChainDictTests:

    def make(self, *args, **kwds):
        return fallback_chain_dict(*args, **kwds)
        
    def test_basic(self):
        make = self.make
        
        o = make(make(make(dict(a=1, b=2), c=3, d=4), e=5, f=6), c=3.5, g=7, h=8)
        d = dict(a=1, b=2, c=3.5, d=4, e=5, f=6, g=7, h=8)

        assert len(o) == len(d)
        assert dict(o) == d
        assert tuple(o) == tuple(d)
        assert tuple(o.keys()) == tuple(d.keys())
        assert tuple(o.values()) == tuple(d.values())
        assert tuple(o.items()) == tuple(d.items())

        assert all((k in o) for k in 'abcdefgh')
        assert all((k not in o) for k in 'xyz')
        assert {*'cgh'} == o.ownkeys()


    def test_speed(self, speed_profiler):
        make = self.make
        profile = speed_profiler(int(2.5e4), labels=('Ch', 'Fb'))

        o = make(make(make(make(make(dict(a=1, b=2), c=3, d=4), e=5, f=6), g=7, h=8), i=9, j=10), c=3.5, k=11, l=12)
        d = dict(a=1, b=2, c=3.5, d=4, e=5, f=6, g=7, h=8, i=9, j=10, k=11, l=12)

        ch = ChainMap(dict(c=3.5, k=11, l=12), dict(i=9, j=10), dict(g=7, h=8), dict(e=5, f=6), dict(c=3, d=4), dict(a=1, b=2))

        assert len(o) == len(ch) == len(d)
        assert dict(o) == dict(ch) == d

        profile(lambda: len(o), lambda: len(ch), 'len')
        profile(lambda: dict(o), lambda: dict(ch), 'dict')
        profile(lambda: [*o], lambda: [*ch], 'iter')
        profile(lambda: [*o.keys()], lambda: [*ch.keys()], 'keys')
        profile(lambda: [*o.items()], lambda: [*ch.items()], 'items')

        print('')
        profile(lambda: [*(o[k] for k in 'abcdefghijkl')], lambda: [*(ch[k] for k in 'abcdefghijkl')], '__getitem__')
        profile(lambda: [*(o[k] for k in 'ckl')], lambda: [*(ch[k] for k in 'ckl')], '__getitem[0]__')
        profile(lambda: [*(o[k] for k in 'ij')], lambda: [*(ch[k] for k in 'ij')], '__getitem[1]__')
        profile(lambda: [*(o[k] for k in 'gh')], lambda: [*(ch[k] for k in 'gh')], '__getitem[2]__')
        profile(lambda: [*(o[k] for k in 'ef')], lambda: [*(ch[k] for k in 'ef')], '__getitem[3]__')
        profile(lambda: [*(o[k] for k in 'cd')], lambda: [*(ch[k] for k in 'cd')], '__getitem[4]__')
        profile(lambda: [*(o[k] for k in 'ab')], lambda: [*(ch[k] for k in 'ab')], '__getitem[5]__')

        print('')
        profile(lambda: [*((k in o) for k in 'abcdefghijkl')], lambda: [*((k in ch) for k in 'abcdefghijkl')], '__contains__')
        profile(lambda: [*((k in o) for k in 'ghijkl')], lambda: [*((k in ch) for k in 'ghijkl')], '__contains[0]__')
        profile(lambda: [*((k in o) for k in 'abcdef')], lambda: [*((k in ch) for k in 'abcdef')], '__contains[1]__')

        assert 0, d
 
 