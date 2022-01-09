import pytest


from pathlib import Path
from timeit import repeat
from statistics import mean


from ..json import dumps, JsonOpt, loads

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



base = Path(__file__).parent / 'json_test_data'
paths = [base/f for f in ('twitter.json', 'github.json')]


def ops_per_sec(n, *vals):
    val = mean(vals)
    return n * (1/val), val, sum(vals, 0)




class JsonTests:

    def test_bytes_vs_str(self):
        for path in paths:
            raw = path.read_bytes()
            assert raw.decode().encode() == raw
            data = loads(raw)
            n = int(.5e3)
            bfunc = lambda: dumps(data)
            sfunc = lambda: dumps(data, opts=JsonOpt.DECODE)

            self.run(f'{path.name} ({round(len(raw)/1000, 2)}kb)', bfunc, sfunc, n)
            print(' ')


        # assert 0

    def run(self, lbl, mfn, ifn, n=int(1e3), rep=2, r=3):
        mres, mt, mtt = ops_per_sec(n, *repeat(mfn, number=n, repeat=rep, globals=locals()))
        ires, it, itt = ops_per_sec(n, *repeat(ifn, number=n, repeat=rep, globals=locals()))
        if mres > ires:
            d = f'B {round(mres/ires, r)}x faster'
        else:
            d = f'S {round(ires/mres, r)}x faster'
        M, I = f'{round(mtt, r)} secs'.ljust(12) + f' avg {round(mt, r)} secs'.ljust(16) \
                    + f'{round(mres, r)} ops/sec'.ljust(16+r), \
                f'{round(itt, r)} secs'.ljust(12) + f' avg {round(it, r)} secs'.ljust(16) \
                    + f'{round(ires, r)} ops/sec'.ljust(16+r)
        print(f'{lbl}\n {rep} x {n} ({rep * n}) ops == {d}\n   - B={M!s}\n   - S={I!s}')

