"""Dependency Injector Factory providers benchmark."""

import asyncio
import time
from functools import reduce
from operator import or_

from dependency_injector import containers, providers, wiring
from laza.di import Injector, context, inject

from _benchmarkutil import Benchmark

N = int(2e3)
N = 1

ST = 0# .000000001

res: dict[str, tuple[float, float]] = {}


class A(object):
    
    n = 0

    def __init__(self):
        # print(f'{self.__class__.__name__}.new()')
        # time.sleep(ST/2)
        return

class B(object):
    
    n = 0
    
    def __init__(self, a: A):
        assert isinstance(a, A)
        self.a = a
        # self.__class__.n += 1


    @classmethod
    async def make(cls, a: A, /):
        # print(f'{cls.__name__}.make()')
        # await asyncio.sleep(ST)
        rv = cls(a)
        return rv



class C(object):

    def __init__(self, a: A, /, b: B):
        assert isinstance(a, A)
        assert isinstance(b, B)
        # assert isinstance(bb, B)
        # assert b is bb
        self.a = a
        self.b = b

    @classmethod
    async def make(cls, a: A, b: B):
        # print(f'{cls.__name__}.make()')
        # await asyncio.sleep(ST)
        rv = cls(a, b)
        return rv




class Test(object):

   
    def __init__(self, a: A, b: B, /, c: C):
        # time.sleep(ST)

        assert isinstance(a, A)
        assert isinstance(b, B)
        assert isinstance(c, C)
        # assert all(isinstance(_, C) for _ in (c, cc, ccc))
        # assert not (c is cc or c is ccc or cc is ccc)
        # assert b is c.b

        self.a = a
        self.b = b
        self.c = c

    @classmethod
    async def make(cls, a: A, b: B, /, c: C):
        # await asyncio.sleep(0)
        rv = cls(a, b, c)
        return rv




ioc = Injector()

ioc.factory(A)
ioc.factory(B).using(B.make)#.singleton()
ioc.factory(C).using(C.make)#.singleton()
ioc.factory(Test).using(Test.make)  # .singleton()

# Singleton = providers.Singleton 
Singleton = providers.Factory 

class Container(containers.DeclarativeContainer):
    a = providers.Factory(A)
    b = Singleton(B.make, a)
    c = Singleton(C.make, a, b=b)
    test = providers.Factory(
        Test.make,
        a,
        b,
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
    # print('init...')
    # aw = c.c()
    # await asyncio.sleep(1)
    # print('created...')
    # await aw
    # print('done...')

    with context(ioc) as ctx:
        ls = []
       
        pre =None # lambda k, b: print(f'----------------{k}--------------')
        bench = await Benchmark("B.", N).arun(pre, di=Container.b, laza=ctx[B])
        ls.append(bench)
        print(bench, "\n")


        bench = await Benchmark("C.", N).arun(pre, di=Container.c, laza=ctx[C])
        ls.append(bench)
        print(bench, "\n")

        bench = await Benchmark("Test.", N).arun(pre, di=Container.test, laza=ctx[Test])
        ls.append(bench)
        print(bench, "\n")


        print('----------------------------------------')
        # fut = c.test()
        fut = ctx[Test]()
        # await asyncio.sleep(1.25)
        print(f'{fut}')
        print('----------------------------------------')
        # print(f'{await fut}')
        # print(f'{await fut=}')
        # print(f'{await fut=}')

        # bench = Benchmark(f"Providers[{A | B | C | Test}]", N)
        # bench |= reduce(or_, ls)
        # print(bench, "\n")

        # b = await Benchmark("inject.", N).arun(pre, di=_inj_di, laza=_inj_laza)
        # print(b, "\n")


if __name__ == '__main__':
    import uvloop

    # uvloop.install()

  
    asyncio.run(main(), debug=False)
