from itertools import chain
from types import LambdaType
import pytest
import typing as t

from timeit import repeat
from statistics import median, median_high, mean



@pytest.fixture(scope='session')
def ops_per_sec():
    return _ops_per_sec



def _ops_per_sec(n, *vals):
    val = mean(vals)
    return n * (1/val), val, sum(vals, 0)





@pytest.fixture(scope='function')
def speed_profiler(ops_per_sec):

    def _profiler(title, fn1, fn2=None, n=1e4, r=2, lbls=(), g=None, dec=2):
        ...

    @t.overload
    def make(n=int(1e4), globals:dict=None, *, repeat=2, title=None, labels=('a', 'b'), dec: int=3):
        return _profiler

    def make(n_=int(1e4), g_=None, /, **kwds):
        from djx.common.utils._functools import calling_frame
        if g_ is None:
            g_ = dict(calling_frame(locals=True))

        kwds = {**dict(n=n_, globals=g_, title=None, repeat=2, labels=(), dec=3), **kwds}

        def profiler(fn1, fn2=None, title=kwds['title'], n=kwds['n'], r=kwds['repeat'], lbls=kwds['labels'], g=kwds['globals'], dec=kwds['dec']):
            lbls = (lbls,) if isinstance(lbls, str) else tuple(lbls or ())
            if fn2 is None:
                fn2 = fn1
                if not lbls:
                    lbls = f'{"func_1" if isinstance(fn1, LambdaType) else fn1.__name__}',

            if len(lbls) > 1:
                lbl1, lbl2 = lbls
            elif lbls:
                lbl1, lbl2 = (f'{lbls[0]}__A', f'{lbls[0]}__B')
            else:
                lbl1, lbl2 = (f'{"func_1" if isinstance(fn1, LambdaType) else fn1.__name__}', f'{"func_2" if isinstance(fn2, LambdaType) else fn2.__name__}')
                
            res1, t1, tt1 = ops_per_sec(n, *repeat(fn1, number=n, repeat=r, globals=g))
            res2, t2, tt2 = ops_per_sec(n, *repeat(fn2, number=n, repeat=r, globals=g))

            if res1 > res2:
                d = f'{lbl1} {round(res1/res2, dec)}x faster'
            else:
                d = f'{lbl2}  {round(res2/res1, dec)}x faster'
            a, b = f'{round(tt1, dec)} secs'.ljust(12) + f' avg {round(t1, dec)} secs'.ljust(16) \
                        + f'{round(res1, dec)} ops/sec'.ljust(16+dec), \
                    f'{round(tt2, dec)} secs'.ljust(12) + f' avg {round(t2, dec)} secs'.ljust(16) \
                        + f'{round(res2, dec)} ops/sec'.ljust(16+dec)

            print(f' - {title or f"{lbl1}-vs-{lbl2}"}[{r}x{n}={r * n}ops] {d}\n   - {lbl1}={a!s}\n   - {lbl2}={b!s}')
        return profiler

    return make
