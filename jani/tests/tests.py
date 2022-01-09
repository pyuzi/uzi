from contextlib import nullcontext



import typing as t

from memory_profiler import profile
import pytest



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




class MiscTests:

        
    def test_closure_speed(self, speed_profiler):

        from types import MethodType
        class Foo:

            __slots__ = ('call',)

            def __init__(self):

                def call(a, b):
                    return a ** b

                self.call = call

            def run(self, a, b):
                return a ** b

            def __call__(self):
                self.run(9e3, 10)


        def meth(self):
            self.run(9e3, 10)

        def make_method():
            return MethodType(meth, foo)
        
        # def make_method():
        #     nonlocal foo
        #     return lambda: Foo.run(foo, 9e3, 10)

        def make_method():
            nonlocal foo
            def meth():
                nonlocal foo
                foo.run(9e3, 10)

            return meth

        def make_closure():
            nonlocal foo
            return lambda: foo.run(9e3, 10)
            # def meth(*args):
            #     nonlocal foo, run
            #     run(foo, 9e3, 10)

            # return meth

        def make_obj():
            return Foo()

        foo = Foo()

        _n = int(5e4)
        spro = speed_profiler(_n, labels=('Obj', 'Fun'), repeat=5)
        
        spro(make_method, make_closure, 'Make')
        spro(make_method(), make_closure(), 'Call')

        spro = speed_profiler(_n, labels=('Fun', 'Obj'), repeat=5)

        spro(make_closure, make_method, 'Make')
        spro(make_closure(), make_method(), 'Call')

        assert 0

        



