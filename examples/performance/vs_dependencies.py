"""Dependency Injector Factory providers benchmark."""

from collections import defaultdict
from fcntl import ioctl
import time

import dependencies

from laza.di.injectors import Injector, inject
from laza.di.context import wire




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

    def some(self):
        print(f'Test[{id(self)}]')

# ioc = Injector()

# ioc.provide(A, B, C, Test)



# @inject
# def _inj(test: Test, b: B, c: C):
#     assert isinstance(test, Test)
#     # assert isinstance(a, A)
#     assert isinstance(b, B)
#     assert isinstance(c, C)



class Container(dependencies.Injector):
    test = Test
    a = A
    b = B
    c = C



Container.test.some()
Container.test.some()




def test_simple_factory_provider():
    return Test(a=A(), b=B(A()), c=C(A(), B(A())))


start = time.time()
for _ in range(1, N):
    test_simple_factory_provider()
finish = time.time()

took = finish - start
res['py'] = took, N*(1/took)


