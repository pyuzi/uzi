"""Dependency Injector Factory providers benchmark."""

import asyncio
from functools import reduce
from operator import or_

from dependency_injector import containers, providers, wiring
from laza.di import Injector, context, inject

from _benchmarkutil import Benchmark

N = int(2.5e3)

res: dict[str, tuple[float, float]] = {}


class A(object):
    
    n = 0

    def __init__(self):
        pass


class B(object):
    
    n = 0
    
    def __init__(self, a: A):
        assert isinstance(a, A)
        self.a = a
        self.__class__.n += 1
        # print(f'{self.__class__.__name__}.new({self.n})')


    @classmethod
    async def make(cls, a: A):
        # print(f'{cls.__name__}.making...')
        await asyncio.sleep(.00001)
        rv = cls(a)
        # print(f'{cls.__name__}.done({rv.n})')
        return rv



class C(object):

    def __init__(self, a: A, b: B):
        assert isinstance(a, A)
        assert isinstance(b, B)
        # assert isinstance(bb, B)
        # assert b is bb
        self.a = a
        self.b = b


class Test(object):

   
    def __init__(self, a: A, b: B, c: C):

        assert isinstance(a, A)
        assert isinstance(b, B)
        assert isinstance(c, C)
        # assert all(isinstance(_, C) for _ in (c, cc, ccc))
        # assert not (c is cc or c is ccc or cc is ccc)
        # assert b is c.b

        self.a = a
        self.b = b
        self.c = c



ioc = Injector()

ioc.factory(A)
ioc.factory(B).using(B.make).asynchronous()#.singleton()
ioc.factory(C)#.using(C.make)#.singleton()
ioc.factory(Test)#.using(Test.make)  # .singleton()

# Singleton = providers.Singleton 
Singleton = providers.Factory 

class Container(containers.DeclarativeContainer):
    a = providers.Factory(A)
    b = Singleton(B.make, a)
    c = Singleton(C, a, b)
    test = providers.Factory(
        Test,
        a=a,
        b=b,
        c=c,
    )


@inject
async def _inj_laza(test: Test, a: A, b: B, c: C):
    assert isinstance(test, Test)
    assert isinstance(a, A)
    assert isinstance(b, B)
    assert isinstance(c, C)


@wiring.inject
async def _inj_di(
    test: Test = wiring.Provide[Container.test],
    a: Test = wiring.Provide[Container.a],
    b: Test = wiring.Provide[Container.b],
    c: Test = wiring.Provide[Container.c],
):
    assert isinstance(test, Test)
    assert isinstance(a, A)
    assert isinstance(b, B)
    assert isinstance(c, C)


c = Container()
c.wire([__name__])

async def main():
    with context(ioc) as ctx:
        ls = []
       
        pre =None # lambda k, b: print(f'----------------{k}--------------')
        bench = await Benchmark("B.", N).arun(pre, di=Container.b, laza=lambda x=ctx[B]: x())
        ls.append(bench)
        print(bench, "\n")

        bench = await Benchmark("C.", N).arun(pre, di=Container.c, laza=lambda: ctx[C]())
        ls.append(bench)
        print(bench, "\n")

        bench = await Benchmark("Test.", N).arun(pre, di=Container.test, laza=lambda: ctx[Test]())
        ls.append(bench)
        print(bench, "\n")

        # bench = Benchmark(f"Providers[{A | B | C | Test}]", N)
        # bench |= reduce(or_, ls)
        # print(bench, "\n")

        # b = await Benchmark("inject.", N).arun(pre, di=_inj_di, laza=_inj_laza)
        # print(b, "\n")


if __name__ == '__main__':
    asyncio.run(main(), debug=True)
