from pprint import pprint
from time import time
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
            assert isinstance(inj[Foo](), Foo)
            assert isinstance(inj[Bar](), Bar)
            assert isinstance(inj[Baz](), Baz)
            assert inj[Foo]() is not inj[Foo]()

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

        ioc.type(Foo)#.singleton()
        ioc.type(Bar).singleton()
        ioc.type(Baz).singleton()
        ioc.type(FooBar)#.singleton()
        ioc.type(FooBarBaz)#.singleton()
        ioc.type(Service)#.singleton()


        @ioc.inject
        def inject_1(baz: Baz, /):
            assert isinstance(baz, Baz)
            return baz

        @ioc.inject
        def inject_2(foo: Foo, bar: Bar, baz: Baz):
            assert isinstance(foo, Foo)
            assert isinstance(bar, Bar)
            assert isinstance(baz, Baz)
            return foo, bar, baz

        @ioc.inject
        def inject_3(foobar: FooBar, foobarbaz: FooBarBaz, /, service: Service):
            assert isinstance(foobar, FooBar)
            assert isinstance(foobarbaz, FooBarBaz)
            assert isinstance(service, Service)
            return foobar, foobarbaz, service
        _tap = lambda x=True: x and None
        mkfoo = lambda: Foo()
        mkbar = lambda: Bar(mkfoo())
        mkbaz = lambda: Baz(mkbar())
        mkfoobar = lambda: FooBar(mkfoo(), mkbar())
        mkfoobarbaz = lambda: FooBarBaz(mkfoo(), mkbar(), mkbaz())
        mkservice = lambda: Service(mkfoo(), mkbar(), mkbaz(), mkfoobar(), mkfoobarbaz())

        mkinject_1 = lambda: inject_1.__wrapped__(mkbaz())
        mkinject_2 = lambda: inject_2.__wrapped__(mkfoo(), mkbar(), mkbaz())
        mkinject_3 = lambda: inject_3.__wrapped__(mkfoobar(), mkfoobarbaz(), mkservice())

        _n = int(2.5e2)
        _r = 4
        profile = speed_profiler(_n, labels=('PY', 'DI'), repeat=_r)
        xprofile = speed_profiler(_n, labels=('DI', 'PY'), repeat=_r)

        t = time()
        with ioc.make() as inj:

            infoo = lambda: inj[Foo]()
            inbar = lambda: inj[Bar]()
            inbaz = lambda: inj[Baz]()
            infoobar = lambda: inj[FooBar]()
            infoobarbaz = lambda: inj[FooBarBaz]()
            inservice = lambda: inj[Service]()

            print('')

            infoo(), inbar(), inbaz(), infoobar(), infoobarbaz(), inservice()
            # assert 0

            profile(mkfoo, inj[Foo], 'Foo')
            profile(mkbar, inj[Bar], 'Bar')
            profile(mkbaz, inj[Baz], 'Baz')

            profile(mkfoobar, inj[FooBar], 'FooBar')
            profile(mkfoobarbaz, inj[FooBarBaz], 'FooBarBaz')


            profile(mkservice, inj[Service], 'Service')

            profile(mkinject_1, inject_1, inject_1.__name__)
            profile(mkinject_2, inject_2, inject_2.__name__)
            profile(mkinject_3, inject_3, inject_3.__name__)

            # xprofile(inject_1, mkinject_1, inject_1.__name__)
            # xprofile(inject_2, mkinject_2, inject_2.__name__)

            print(*inject_2())


            print(f'TOTAL TIME: {round(time()-t, 4):,} secs')

        assert 0, '\n'
 
   


class Foo:
     def __init__(self) -> None:
        pass

    
class Bar:
    
    def __init__(self, foo: Foo, /) -> None:
        assert isinstance(foo, Foo)

     
class Baz:
    
    def __init__(self, bar: Bar, /) -> None:
        assert isinstance(bar, Bar)


 
class FooBar:
    
    def __init__(self, foo: Foo, bar: Bar, /) -> None:
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)



class FooBarBaz:
    
    def __init__(self, foo: Foo, bar: Bar, baz: Baz, /) -> None:
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)
        assert isinstance(baz, Baz)
    



class Service:
    
    def __init__(self, foo: Foo, bar: Bar, baz: Baz, /, foobar: FooBar, foobarbaz: FooBarBaz) -> None:
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)
        assert isinstance(baz, Baz)
        assert isinstance(foobar, FooBar)
        assert isinstance(foobarbaz, FooBarBaz)

