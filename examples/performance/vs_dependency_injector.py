"""Dependency Injector Factory providers benchmark."""
import time
from functools import reduce
from operator import or_
from typing import Literal

from dependency_injector import containers, providers, wiring, resources
from xdi import Injector, context, inject

from _benchmarkutil import Benchmark

N = int(5e3)
# N = 1

res: dict[str, tuple[float, float]] = {}



class A(object):
    def __init__(self):
        ls = [*range(100)]


class B(object):
    def __init__(self, a: A, /):
        ls = [*range(50)]
        assert isinstance(a, A)

    @classmethod
    async def make(cls, a: A, /):
        rv = cls(a)
        return rv



class C(object):
    def __init__(self, a: A, /, b: B):
        assert isinstance(a, A)
        assert isinstance(b, B)

    @classmethod
    async def make(cls, a: A, b: B):
        rv = cls(a, b)
        return rv


class Connection:

    state: Literal['pending', 'opened', 'closed'] = None
    n = 0
    g = 0
    is_async = None

    def __init__(self, a: A, /, b: B, *, k='con-'):
        assert isinstance(a, A)
        self.__class__.n += 1
        self.id = f'{k}{self.__class__.n}'
        self.state = 'pending'

    @classmethod
    def iconnect(cls, a: A, /, b: B, *, k='gen-'):
        cls.g += 1
        self = cls(a, b, k=k)
        yield self.__enter__()
        return self.__exit__(None, None, None)
    
    def __repr__(self):
        is_async = self.is_async
        return f'{self.__class__.__name__} #{self.id}: {self.state!r} {is_async=}'

    def __enter__(self):
        self.is_async = False
        return self.initialize()

    def __exit__(self, *err):
        assert self.is_async is False
        return self.dispose(*err)

    async def __aenter__(self):
        self.is_async = True
        return self.initialize()

    async def __aexit__(self, *err):
        assert self.is_async
        return self.dispose(*err)

    def initialize(self):
        if self.state == 'pending':
            self.state = 'opened'
            print(f'{self!r}')
        else:
            print(f'Invalid state: {self!r}')
        return self

    def dispose(self, *err):
        if self.state == 'opened':
            self.state = 'closed'
            print(f'{self!r}')
        else:
            print(f'Invalid state: {self!r}')

    def __del__(self):
        print(f'__del__ --> {self!r}')




class Test(object):
    def __init__(self, x, y, z, a: A, /, b: B, c: C, con: Connection, **kw): # x: str=None, y:str=None, z: str=None):

        assert isinstance(a, A)
        assert isinstance(b, B)
        assert isinstance(c, C)
        assert isinstance(con, Connection)
        # assert con is con2
        # assert ('x', 'y', 'z') == tuple(kw)

        self.a = a
        self.b = b
        self.c = c

    @classmethod
    async def make(cls, x, y, z, a: A, /, b: B, c: C, con: Connection, **kw):
        rv = cls(x, y, z, a, b, c, con, **kw)
        return rv



ioc = Injector()

ioc.factory(A)
ioc.factory(B)#.singleton()
ioc.singleton(C)#.singleton()
ioc.resource(Connection, k='cm-')
ioc.factory(Test).args('ex','why','zee').kwargs(x='ex', y='why', z='zee')  # .singleton()


Singleton = providers.Singleton 
# Singleton = providers.Factory 

class Container(containers.DeclarativeContainer):
    a = providers.Factory(A)
    b = providers.Factory(B, a)
    # b = Singleton(B, a)
    con = providers.Resource(Connection.iconnect, a, b=b, k='gn-')
    c = Singleton(C, a, b=b)
    test = providers.Factory(
        Test,
        'ex','why','zee', 
        # A(),
        a,
        b=b,
        c=c,
        con=con,
        # con2=con,
        x='ex',
        y='why',
        z='zee'
    )


@inject
def _inj_xdi(test: Test, a: A, b: B, c: C):
    assert isinstance(test, Test)
    assert isinstance(a, A)
    assert isinstance(b, B)
    assert isinstance(c, C)

def _new_ctx_test():
    with context(ioc) as ctx:
        test = ctx[Test]()
        

def _new_ctx_inj():
    with context(ioc) as ctx:
        _inj_xdi()
        

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


def main():

    c = Container()
    c.wire([__name__])
    c.init_resources()

    with context(ioc) as ctx:
       

        ls = []
       
        
        
        bench = Benchmark("A.", N).run(di=Container.a, xdi=ctx[A])
        # ls.append(bench)
        print(bench, "\n")

        bench = Benchmark("B.", N).run( di=Container.b, xdi=ctx[B])
        ls.append(bench)
        print(bench, "\n")

        bench = Benchmark("C.", N).run(di=Container.c, xdi=ctx[C])
        ls.append(bench)
        print(bench, "\n")

        bench = Benchmark("Test.", N).run(di=Container.test, xdi=ctx[Test])
        ls.append(bench)
        print(bench, "\n")

        bench = Benchmark("inject.", N).run(di=_inj_di, xdi=_inj_xdi)
        ls.append(bench)
        print(bench, "\n")


        bench = Benchmark(f"Providers[{A | B | C | Test}]", N)
        bench |= reduce(or_, ls)
        print(bench, "\n")

           
    c.shutdown_resources()

    # b = Benchmark("new-ctx.test.", N).run(di=lambda: c.test(), xdi=_new_ctx_test)
    # print(b)
    # b = Benchmark("new-ctx.inject.", N).run(di=_inj_di, xdi=_new_ctx_inj)
    # print(b, "\n")


if __name__ == '__main__':
    main()
