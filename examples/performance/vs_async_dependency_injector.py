"""Dependency Injector Factory providers benchmark."""

import asyncio
from functools import reduce
from operator import or_

from dependency_injector import containers, providers, wiring
from laza.di import Injector, context, inject

from _benchmarkutil import Benchmark

N = int(2e4)

res: dict[str, tuple[float, float]] = {}


class A(object):
    def __init__(self):
        pass


class B(object):
    def __init__(self, a: A):
        assert isinstance(a, A)

    @classmethod
    async def make(cls, a: A):
        return await asyncio.sleep(0, cls(a))



class C(object):

    def __init__(self, a: A, b: B):
        assert isinstance(a, A)
        assert isinstance(b, B)

    @classmethod
    async def make(cls, a: A, b: B):
        return await asyncio.sleep(0, cls(a, b))



class Test(object):

    @classmethod
    async def make(cls, a: A, b: B, c: C):
        return await asyncio.sleep(0, cls(a, b, c))

    def __init__(self, a: A, b: B, c: C):

        assert isinstance(a, A)
        assert isinstance(b, B)
        assert isinstance(c, C)

        self.a = a
        self.b = b
        self.c = c



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
    c = Singleton(C.make, a, b)
    test = providers.Factory(
        Test.make,
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
        ls = [
            await Benchmark("B.", N).arun(di=Container.b, laza=ctx[B]),
            await Benchmark("C.", N).arun(di=Container.c, laza=ctx[C]),
            await Benchmark("Test.", N).arun(di=Container.test, laza=ctx[Test]),
        ]

        bench = Benchmark(f"Providers[{A | B | C | Test}]", N)
        bench |= reduce(or_, ls)
        print(bench, "\n")

        b = await Benchmark("inject.", N).arun(di=_inj_di, laza=_inj_laza)
        print(b, "\n")


if __name__ == '__main__':
    asyncio.run(main())
