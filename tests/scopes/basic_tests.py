from pprint import pprint
import pytest

from laza.di.containers import IocContainer
from laza.di.common import InjectionToken
from laza.di.injectors import MainInjector, LocalInjector



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize






class BasicScopeTests:

 
    def test_providers(self):
        con = IocContainer() 

        con.type(Foo)
        # con1[Foo] = p.Type(Foo)

        con.type(Bar)
        con.type(Baz)

        con.type(FooBar, FooBar)
        con.type(FooBarBaz, FooBarBaz)



        scope = MainInjector(con)

        with scope.make() as inj:
            assert isinstance(inj[Foo].get(), Foo)
            assert isinstance(inj[Bar].get(), Bar)
            assert isinstance(inj[Baz].get(), Baz)
            assert inj[Foo].get() is not inj[Foo].get()

        assert 1, '\n'
 
    def _test_inject(self):
        con1 = IocContainer() 

        con1.type(Foo)
        # con1[Foo] = p.Type(Foo)

        con1.type(Bar)
         
        con2 = IocContainer(shared=False) 
        con2.type(Baz)

        con3 = IocContainer(con1, con2) 

        @con3.inject
        def inject_con4(baz: Baz, foo: Foo):
            return baz, foo

        con3.type(FooBar, FooBar)
        con3.type(FooBarBaz, FooBarBaz)

        con4 = IocContainer(con2)

        @con4.inject
        def inject_con4(baz: Baz, foo: Foo):
            return baz, foo


        scope1 = MainInjector(con3)
        scope2 = LocalInjector(scope1)
        scope3 = LocalInjector(scope2, con4)

        with scope2.make() as inj_:
            with scope3.make(inj_) as inj:
                assert all(isinstance(o, c) for o,c in zip(inject_con4(), (Baz, Foo)))
               
        assert 1, '\n'
 
    def test_perfomance(self, speed_profiler):
        ioc = MainInjector() 

        SharedFoo = InjectionToken('SharedFoo')

        ioc.type(Foo)
        ioc.type(SharedFoo).using(Foo).singleton(False)
        ioc.type(Bar).singleton(False)
        ioc.type(Baz).singleton(False)


        @ioc.inject
        def inject_1(baz: Baz):
            assert isinstance(baz, Baz)
            return baz

        @ioc.inject
        def inject_2(foo: Foo, bar: Bar, baz: Baz):
            assert isinstance(foo, Foo)
            assert isinstance(bar, Bar)
            assert isinstance(baz, Baz)
            return foo, bar, baz

        mkfoo = lambda: Foo()
        mkbar = lambda: Bar(mkfoo())
        mkbaz = lambda: Baz(mkbar())

        mkinject_1 = lambda: inject_1.__wrapped__(mkbaz())
        mkinject_2 = lambda: inject_2.__wrapped__(mkfoo(), mkbar(), mkbaz())

        _n = int(2e5)
        _r = 3
        profile = speed_profiler(_n, labels=('PY', 'DI'), repeat=_r)
        xprofile = speed_profiler(_n, labels=('DI', 'PY'), repeat=_r)


        with ioc.make() as inj:

            infoo = lambda: inj[Foo].get()
            insharedfoo = lambda: inj[SharedFoo].get()
            insharedfoo_get = lambda: inj[SharedFoo].get()
            inbar = lambda: inj[Bar].get()
            inbaz = lambda: inj[Baz].get()

            print('')

            infoo()

            profile(mkfoo, infoo, 'Foo')
            profile(mkbar, inbar, 'Bar')
            profile(mkbaz, inbaz, 'Baz')

            print('')

            profile(mkinject_1, inject_1, inject_1.__name__)
            profile(mkinject_2, inject_2, inject_2.__name__)

            print('')

            # xprofile(inject_1, mkinject_1, inject_1.__name__)
            # xprofile(inject_2, mkinject_2, inject_2.__name__)

            print(*inject_2())


            print('')

        assert 0, '\n'
 
   


class Foo:
    ...
    
class Bar:
    
    def __init__(self, foo: Foo) -> None:
        self.foo = foo

     
class Baz:
    
    def __init__(self, bar: Bar) -> None:
        self.bar = bar


 
class FooBar(Foo, Bar):
    ...
     

class FooBarBaz(FooBar, Baz):
    ...
    