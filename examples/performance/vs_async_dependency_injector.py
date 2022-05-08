"""Dependency Injector Factory providers benchmark."""

import asyncio
import time
from functools import reduce
from operator import or_

from dependency_injector import containers, providers, wiring

from _benchmarkutil import Benchmark
from vs_dependency_injector import A, B, C, Test, Connection, Container, ioc
import uzi


# N = 1

ST = 0# .000000001




ioc = uzi.Container()

ioc.factory(A)
ioc.factory(B).use(B.make)#.singleton()
ioc.singleton(C).use(C.make)#.singleton()
ioc.factory(Connection, k='cm-')
ioc.factory(Test).use(Test.make, 'ex','why','zee', x='ex', y='why', z='zee')  # .singleton()


Singleton = providers.Singleton 
# Singleton = providers.Factory 

class Container(containers.DeclarativeContainer):
    a = providers.Factory(A)
    b = providers.Factory(B.make, a)
    # b = Singleton(B.make, a)
    c = Singleton(C.make, a, b=b)
    con = providers.Factory(Connection, a, b=b, k='gn-')
    test = providers.Factory(
        Test.make,
        'ex','why','zee', 
        a, b,
        c=c, con=con,
        x='ex', y='why', z='zee'
    )


# @inject
# async def _inj_uzi(test: Test, a: A, b: B, c: C):
#     assert isinstance(test, Test)
#     assert isinstance(a, A)
#     assert isinstance(b, B)
#     assert isinstance(c, C)


# @wiring.inject
# async def _inj_di(
#     test: Test = wiring.Provide[Container.test],
#     a: Test = wiring.Provide[Container.a],
#     b: Test = wiring.Provide[Container.b],
#     c: Test = wiring.Provide[Container.c],
# ):
#     assert isinstance(test, Test)
#     assert isinstance(a, A)
#     assert isinstance(b, B)
#     assert isinstance(c, C)



async def main():
    N = int(5e3)


    c = Container()
    c.wire([__name__])
    # c.init_resources()

    scope = uzi.DepGraph(ioc)

    if inj := uzi.injectors.Injector(scope):

    # async with context(ioc) as ctx:
        ls = []
       
        pre =None # lambda k, b: print(f'----------------{k}--------------')
        bench = await Benchmark("B.", N).arun(pre, di=Container.b, uzi=inj.bound(B))
        ls.append(bench)
        print(bench, "\n")


        bench = await Benchmark("C.", N).arun(pre, di=Container.c, uzi=inj.bound(C))
        ls.append(bench)
        print(bench, "\n")

        bench = await Benchmark("Test.", N).arun(pre, di=Container.test, uzi=inj.bound(Test))
        ls.append(bench)
        print(bench, "\n")



if __name__ == '__main__':

    print('----------------------------------------')
    print('---         without uvloop           ---')
    print('----------------------------------------')
    asyncio.run(main(), debug=False)


    print('----------------------------------------')
    print('---           with  uvloop           ---')
    print('----------------------------------------')

    import uvloop
    uvloop.install()

    asyncio.run(main(), debug=False)

