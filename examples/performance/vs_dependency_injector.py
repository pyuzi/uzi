"""Dependency Injector Factory providers benchmark."""

from functools import reduce
from operator import or_

from dependency_injector import containers, providers, wiring
from laza.di import Injector, context, inject

from _benchmarkutil import Benchmark

N = int(0.25e6)

res: dict[str, tuple[float, float]] = {}


class A(object):
    def __init__(self):
        pass


class B(object):
    def __init__(self, a: A):
        assert isinstance(a, A)


class C(object):
    def __init__(self, a: A, b: B):
        assert isinstance(a, A)
        assert isinstance(b, B)


class Test(object):
    def __init__(self, a: A, b: B, c: C):

        assert isinstance(a, A)
        assert isinstance(b, B)
        assert isinstance(c, C)

        self.a = a
        self.b = b
        self.c = c


ioc = Injector()

ioc.factory(A)
ioc.factory(B)#.singleton()
ioc.factory(C)#.singleton()
ioc.factory(Test)  # .singleton()


# Singleton = providers.Singleton 
Singleton = providers.Factory 

class Container(containers.DeclarativeContainer):
    a = providers.Factory(A)
    b = Singleton(B, a)
    c = Singleton(C, a, b)
    test = providers.Factory(
        Test,
        a=a,
        b=b,
        c=c,
    )


@inject
def _inj_laza(test: Test, a: A, b: B, c: C):
    assert isinstance(test, Test)
    assert isinstance(a, A)
    assert isinstance(b, B)
    assert isinstance(c, C)


@wiring.inject
def _inj_di(
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


def main():
    with context(ioc) as ctx:
        ls = [
            Benchmark("A.", N).run(di=Container.a, laza=lambda x=ctx[A]: x()),
            Benchmark("B.", N).run(di=Container.b, laza=lambda x=ctx[B]: x()),
            Benchmark("C.", N).run(di=Container.c, laza=lambda x=ctx[C]: x()),
            Benchmark("Test.", N).run(di=Container.test, laza=lambda x=ctx[Test]: x()),
        ]

        bench = Benchmark(f"Providers[{A | B | C | Test}]", N)
        bench |= reduce(or_, ls)
        print(bench, "\n")

        b = Benchmark("inject.", N).run(di=_inj_di, laza=_inj_laza)
        print(b, "\n")


if __name__ == '__main__':
    main()
