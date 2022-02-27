"""Dependency Injector Factory providers benchmark."""

from collections import defaultdict
from fcntl import ioctl
from functools import reduce
from operator import or_
import time

from dependency_injector import providers, containers, wiring

from laza.di.injectors import Injector, inject
from laza.di.context import wire


from _benchmarkutil import Benchmark, Timer


N = int(.25e6)

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
ioc.factory(Test)#.singleton()



test_factory_provider = providers.Factory(
    Test,
    providers.Factory(A),
    b=providers.Factory(B, providers.Factory(A)),
    c=providers.Factory(C, providers.Factory(A), providers.Factory(B, providers.Factory(A))),
)



with wire(ioc) as ctx:
    ls = [
        Benchmark('A.', N).run(VS=providers.Factory(A), DI=ctx[A]),
        Benchmark('B.', N).run(VS=providers.Factory(B, providers.Factory(A)), DI=ctx[B]),
        Benchmark('C.', N).run(VS=providers.Factory(C, providers.Factory(A), providers.Factory(B, providers.Factory(A))), DI=ctx[C]),
        
    ]


    bench = Benchmark(f'Providers[{A | B | C | Test}]', N)
    bench |= reduce(or_, ls)
    print(bench, '\n')

    print(Benchmark('Providers.Test.', N).run(VS=test_factory_provider, DI=ctx[Test]))



@inject
def _inj(test: Test, b: B, c: C):
    assert isinstance(test, Test)
    # assert isinstance(a, A)
    assert isinstance(b, B)
    assert isinstance(c, C)


with wire(ioc):
    print('')

# Testing simple analog

def test_simple_factory_provider():
    return Test(a=A(), b=B(A()), c=C(A(), B(A())))


start = time.time()
for _ in range(1, N):
    test_simple_factory_provider()
finish = time.time()

took = finish - start
res['py'] = took, N*(1/took)


with wire(ioc) as inj:
    start = time.time()
    # v = inj[Test]
    for _ in range(1, N):
        # v()
        inj[Test]()

    finish = time.time()


took = finish - start
res['ioc'] = took, N*(1/took)

start = time.time()
for _ in range(1, N):
    with wire(ioc) as inj:
        inj[Test]()

finish = time.time()

took = finish - start
res['iocx'] = took, N*(1/took)



with wire(ioc) as inj:
    start = time.time()
    _b = B(A())
    for _ in range(1, N):
        _inj(b=_b)

    finish = time.time()

took = finish - start
res['inj'] = took, N*(1/took)


# Testing Factory provider

test_factory_provider = providers.Factory(
    Test,
    providers.Factory(A),
    b=providers.Factory(B, providers.Factory(A)),
    c=providers.Factory(C, providers.Factory(A), providers.Factory(B, providers.Factory(A))),
)



start = time.time()
for _ in range(1, N):
    test_factory_provider()

finish = time.time()
took = finish - start
res['di'] = took, N*(1/took)




class Container(containers.DeclarativeContainer):
    a = providers.Factory(A)
    b = providers.Factory(B, a)
    c = providers.Factory(C, a, b)
    test = providers.Factory(
        Test,
        a=a,
        b=b,
        c=c,
    )




@wiring.inject
def _inj(test: Test= wiring.Provide[Container.test],
        a: Test= wiring.Provide[Container.a],
        b: Test= wiring.Provide[Container.b],
        c: Test= wiring.Provide[Container.c],
):
    assert isinstance(test, Test)
    assert isinstance(a, A)
    assert isinstance(b, B)
    assert isinstance(c, C)


c = Container()
c.wire([__name__])


start = time.time()
_b = B(A())
for _ in range(1, N):
    _inj(b=_b)

finish = time.time()
took = finish - start
res['wire'] = took, N*(1/took)

comp = defaultdict[str, dict[str, str]](dict)
print(f'Results for {N:,} ops')
print(f'   {"TEST".ljust(8)} {f"TIME".rjust(8)} {"OPS/SEC".rjust(12)}')

for k, (t, o) in res.items():
    print(f' - {k.upper().ljust(8)} {f"{round(t, 3):,}".rjust(8)} {f"{round(o):,}".rjust(12)}')
    for x, (xt, xo) in res.items():
        if o > xo:
            comp[k][x] = f'{round(o/xo, 2):,}+'
        elif o < xo:
            comp[k][x] = f'{round(xo/o, 2):,}-'
        elif x == k:
            comp[k][x] = f'... '
        else:
            comp[k][x] = f'{round(xo/o, 2):,} '


print('')    

print(''.ljust(12), *(k.upper().rjust(10) for k in comp))
for k, r in comp.items():
    print(f'   {k.upper().ljust(8)}:', *(v.rjust(10) for v in r.values()))

print('\n')    

# ------
# Result
# ------
#
# Python 2.7
#
# $ python tests/performance/factory_benchmark_1.py
# 0.87456202507
# 0.879760980606
#
# $ python tests/performance/factory_benchmark_1.py
# 0.949290990829
# 0.853044986725
#
# $ python tests/performance/factory_benchmark_1.py
# 0.964688062668
# 0.857432842255
#
# Python 3.7.0
#
# $ python tests/performance/factory_benchmark_1.py
# 1.1037120819091797
# 0.999565839767456
#
# $ python tests/performance/factory_benchmark_1.py
# 1.0855588912963867
# 1.0008318424224854
#
# $ python tests/performance/factory_benchmark_1.py
# 1.0706679821014404
# 1.0106139183044434
