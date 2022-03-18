"""Dependency Injector Factory providers benchmark."""

import asyncio
import time
from functools import reduce
from operator import or_

from dependency_injector import containers, providers, wiring
from laza.di import Injector, context, inject

from _benchmarkutil import Benchmark
from vs_dependency_injector import A, B, C, Test, Connection, Container, ioc



N = int(2e3)
# N = 1

ST = 0# .000000001




ioc = Injector()

ioc.factory(A)
ioc.factory(B).using(B.make)#.singleton()
ioc.singleton(C).using(C.make)#.singleton()
ioc.resource(Connection, k='cm-')
ioc.factory(Test).using(Test.make, 'ex','why','zee', x='ex', y='why', z='zee')  # .singleton()


Singleton = providers.Singleton 
# Singleton = providers.Factory 

class Container(containers.DeclarativeContainer):
    a = providers.Factory(A)
    b = providers.Factory(B.make, a)
    # b = Singleton(B.make, a)
    c = Singleton(C.make, a, b=b)
    con = providers.Resource(Connection, a, b=b, k='gn-')
    test = providers.Factory(
        Test.make,
        'ex','why','zee', 
        a, b,
        c=c, con=con,
        x='ex', y='why', z='zee'
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



async def main():
    # print('init...')
    # aw = c.c()
    # await asyncio.sleep(1)
    # print('created...')
    # await aw
    # print('done...')

    c = Container()
    c.wire([__name__])
    c.init_resources()

    async with context(ioc) as ctx:
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

        b = await Benchmark("inject.", N).arun(pre, di=_inj_di, laza=_inj_laza)
        print(b, "\n")

    c.shutdown_resources()


if __name__ == '__main__':
    import uvloop

    # uvloop.install()

  
    asyncio.run(main(), debug=False)
