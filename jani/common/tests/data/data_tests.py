import pytest



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


from jani.common.utils.data import merge





class BasicTests:

    def test_basic(self):


        d = dict(
                a=1, b=2, c=3.5, d=4, 
                e=5, f=6, g=7, h=8, 
                i=9, j=10, k=11, l=12,
                inner=dict(a=123, b=456, d=[1,2,3])
            )

        ch = [
            dict(
                map=dict(a=1, b=2, c=3, d=4, inner=dict(a=123, b=456, d=[1,2,3])),
                seq=[1,2,3, 4, 5],
            ),
            dict(
                map=dict(e=5, f=6),
                seq=[10,20, 30, 4, 2]
            ), 
            dict(map=dict(g=7, h=8)),
            dict(map=dict(i=9, j=10, inner=dict(a=321, d=[4,5,6]))), 
            dict(map=dict(c=3.5, k=11, l=12)),
        ]

        val = merge({}, *ch, depth=2)

        vardump(**val)

        assert val['map'] == d
        assert 0




