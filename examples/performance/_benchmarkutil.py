from collections import defaultdict
from time import time
import typing as t 


class Timer:

    def __init__(self, ops: int=1):
        self.started_at = self.ended_at = 0
        self.is_error = None
        self.ops = ops or 1

    @property
    def took(self):
        return self.ended_at - self.started_at

    @property
    def rate(self):
        return self.ops*(1/self.took)

    def __enter__(self):
        self.started_at = time()
        return self
    
    def __exit__(self, et=None, *err):
        self.ended_at = time()
        self.is_error = not et is None

    async def __aenter__(self):
        self.started_at = time()
        return self
    
    async def __aexit__(self, et=None, *err):
        self.ended_at = time()
        self.is_error = not et is None

    def __iter__(self):
        yield self.took
        yield self.rate

    def __str__(self) -> str:
        took = round(self.took, 4)
        rate = round(self.rate, 4)
        ops = self.ops
        return f'{took=:,} secs, {rate=:,} ops/sec, {ops:,}'



class Benchmark(dict[str, Timer]):

    def __init__(self, name='TEST', ops: t.Union[int, float] = 1e4):
        self.name = name
        self.ops = int(ops)


    def run(self, func=None, key=None, /, **kw):
        if not func is None:
            kw = { func.__name__ if key is None else key: func }

        ops = self.ops
        ns = f'.{self.name}'.rstrip('.')
        ns = f'{self.name}'

        for k, fn in kw.items():    
            with Timer(ops) as tm:
                for __ in range(ops):
                    fn()

            # self[f'{k}{ns}'] = tm
            self[f'{ns}{k}'] = tm
        return self

    async def arun(self, func=None, key=None, /, **kw):
        if not func is None:
            kw = { func.__name__ if key is None else key: func }

        ops = self.ops
        ns = f'.{self.name}'.rstrip('.')
        ns = f'{self.name}'

        for k, fn in kw.items():    
            async with Timer(ops) as tm:
                for __ in range(ops):
                    await fn()

            # self[f'{k}{ns}'] = tm
            self[f'{ns}{k}'] = tm
        return self

    def __repr__(self):
        self = self
        comp = defaultdict[str, dict[str, str]](dict)
        ops = self.ops
        res = [f'{self.__class__.__name__}({self.name!r})']
       

        klen = max(min(max(map(len, self)), 32), 2) + 2

        res.append(f'   {"TEST".ljust(klen)} {f"TIME".rjust(8)} {"OPS/SEC".rjust(12)}')

        for k, (t, o) in self.items():
            res.append(f' - {k.ljust(klen)} {f"{round(t, 3):,}".rjust(8)} {f"{round(o):,}".rjust(12)}')
            for x, (xt, xo) in self.items():
                if o > xo:
                    comp[k][x] = f'{round(o/xo, 2):,}+'
                elif o < xo:
                    comp[k][x] = f'{round(xo/o, 2):,}-'
                elif x == k:
                    comp[k][x] = f'... '
                else:
                    comp[k][x] = f'{round(xo/o, 2):,} '

        res.append('')    

        res.append(' '.join([''.ljust(klen+4), *(k.rjust(klen) for k in comp)]))
        for k, r in comp.items():
            res.append(' '.join([f'   {k.ljust(klen)}:', *(v.rjust(klen) for v in r.values())]))


        time = round(sum((v.took for v in self.values())), 3)
        ml = max(max(map(len, res)), 20)+2
        res.append('-'*ml)
        res.append(f'  {ops:,} ops in {time:,} secs')
        res.append('='*ml)

        return '\n'.join(res)

    def __str__(self) -> str:
        return self.__repr__()

