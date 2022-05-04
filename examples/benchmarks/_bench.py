from collections import defaultdict
from functools import cache
from time import time
import typing as t 



class Foo:
    def __init__(self) -> None:
        pass

    @staticmethod
    def _make_raw():
        return Foo()

    
class Bar:
    
    def __init__(self, foo: Foo) -> None:
        assert isinstance(foo, Foo)

    @staticmethod
    def _make_raw():
        return Bar(Foo._make_raw())

     
class Baz:   
    def __init__(self, bar: Bar) -> None:
        assert isinstance(bar, Bar)

    @staticmethod
    def _make_raw():
        return Baz(Bar._make_raw())


 
class FooBar:
    
    def __init__(self, foo: Foo, bar: Bar, /) -> None:
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)

    @staticmethod
    @cache
    def _make_raw():
        return FooBar(Foo._make_raw(), Bar._make_raw())



class FooBarBaz:
    
    def __init__(self, foo: Foo, bar: Bar, baz: Baz, /) -> None:
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)
        assert isinstance(baz, Baz)
    
    @staticmethod
    @cache
    def _make_raw():
        return FooBarBaz(Foo._make_raw(), Bar._make_raw(), Baz._make_raw())





class Service:
    
    def __init__(self, foo: Foo, bar: Bar, baz: Baz, foobar: FooBar, foobarbaz: FooBarBaz) -> None:
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)
        assert isinstance(baz, Baz)
        assert isinstance(foobar, FooBar)
        assert isinstance(foobarbaz, FooBarBaz)
    
    @staticmethod
    def _make_raw():
        return Service(Foo._make_raw(), Bar._make_raw(), Baz._make_raw(), FooBar._make_raw(), FooBarBaz._make_raw())



ALL_DEPS = {
    Foo: (),
    Bar: (Foo,),
    Baz: (Bar,),
    FooBar: (Foo, Bar),
    FooBarBaz: (Foo, Bar, Baz,),
    Service: (Foo, Bar, Baz, FooBar, FooBarBaz),
}

SINGLETON_DEPS = [
    FooBar,
    FooBarBaz,
]

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

    def __gt__(self, x):
        return self.took > x

    def __ge__(self, x):
        return self.took >= x

    def __lt__(self, x):
        return self.took < x

    def __le__(self, x):
        return self.took <= x


class Benchmark(dict[str, Timer]):

    def __init__(self, ops: t.Union[int, float] = 1e4, name=''):
        self.name = name
        self.ops = int(ops)

    def sorted(self, *, reverse=False):
        b = self.__class__(self.ops, self.name)
        b |= { k: v for k,v in sorted(self.items(), key=lambda kv: kv[1], reverse=reverse) }
        return b

    def run(self, func=None, key=None, pre=None, /, **kw):
        if not func is None:
            if kw:
                pre = func
            else:
                kw = { func.__name__ if key is None else key: func }

        ops = self.ops
        ns = f'.{self.name}'.rstrip('.')
        ns = f'{self.name}'

        for k, fn in kw.items():    
            pre and pre(k, self)
            with Timer(ops) as tm:
                for __ in range(ops):
                    fn()
            # self[f'{k}{ns}'] = tm
            self[f'{ns}{k}'] = tm
        return self

    async def arun(self, func=None, key=None, pre=None, /, **kw):
        if not func is None:
            if kw:
                pre = func
            else:
                kw = { func.__name__ if key is None else key: func }

        ops = self.ops
        ns = f'.{self.name}'.rstrip('.')
        ns = f'{self.name}'

        for k, fn in kw.items():    
            pre and pre(k, self)
            with Timer(ops) as tm:
                for __ in range(ops):
                    await fn()
            # self[f'{k}{ns}'] = tm
            self[f'{ns}{k}'] = tm
        return self

    def __repr__(self):
        self = self
        comp = defaultdict[str, dict[str, str]](dict)
        ops = self.ops
        res = [f'{self.__class__.__name__}{self.name and f"({self.name!r})"}']
       

        klen = max(min(max(map(len, self)), 32), 2) + 2

        recs = {}

        for k, (t, o) in self.items():
            recs[k] = f' - {k.ljust(klen)} {f"{round(t, 3):,}".rjust(8)} {f"{round(o):,}".rjust(12)}'
            for x, (xt, xo) in self.items():
                if o > xo:
                    comp[k][x] = f'{round(o/xo, 2):,}+'
                elif o < xo:
                    comp[k][x] = f'{round(xo/o, 2):,}-'
                elif x == k:
                    comp[k][x] = f'... '
                    continue
                else:
                    comp[k][x] = f'{round(xo/o, 2):,} '
                x_ = x
            # line = f' - {k.ljust(klen)} {f"{round(t, 3):,}".rjust(8)} {f"{round(o):,}".rjust(12)}'
            # if bi:
            #     line = f"{line} {comp}"
            # res.append()

        # res.append('')    

        res.append(f'   {"TEST".ljust(klen)} {f"TIME".rjust(8)} {"OPS/SEC".rjust(12)} {" ".join(k.rjust(klen) for k in comp)}')
       
        # res.append(' '.join([''.ljust(klen+4), *(k.rjust(klen) for k in comp)]))
        for k, r in comp.items():
            res.append(' '.join([recs[k], *(v.rjust(klen) for v in r.values())]))


        time = round(sum((v.took for v in self.values())), 3)
        ml = max(max(map(len, res)), 20)+2
        res.append('-'*ml)
        res.append(f'  {ops:,} ops in {time:,} secs')
        res.append('='*ml)

        return '\n'.join(res)

    def __str__(self) -> str:
        return self.__repr__()

