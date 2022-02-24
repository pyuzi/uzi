from pprint import pprint
from time import time
import pytest

from laza.di.containers import Container
from laza.di.injectors import Injector, inject, wire


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize





class BasicScopeTests:

 
    def test_providers(self, container):
        container = container

        container.factory(Foo)
        # con1[Foo] = p.Type(Foo)

        container.factory(Bar)
        container.factory(Baz)

        container.factory(FooBar, FooBar)
        container.factory(FooBarBaz, FooBarBaz)

        inj = Injector().require(container)

        with wire(inj) as ctx:
            assert isinstance(ctx[Foo](), Foo)
            assert isinstance(ctx[Bar](), Bar)
            assert isinstance(ctx[Baz](), Baz)
            assert ctx[Foo]() is not ctx[Foo]()

        assert 1, '\n'
 
    def test_perfomance(self, speed_profiler):
        ioc = Injector() 

        ioc.factory(Foo)#.singleton()
        ioc.factory(Bar).singleton()
        ioc.factory(Baz).singleton()
        ioc.factory(FooBar)#.singleton()
        ioc.factory(FooBarBaz)#.singleton()
        ioc.factory(Service)#.singleton()


        @inject
        def inject_1(baz: Baz, /):
            assert isinstance(baz, Baz)
            return baz

        @inject
        def inject_2(foo: Foo, bar: Bar, baz: Baz):
            assert isinstance(foo, Foo)
            assert isinstance(bar, Bar)
            assert isinstance(baz, Baz)
            return foo, bar, baz

        @inject
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
        with wire(ioc) as ctx:
            
            infoo = lambda: ctx[Foo]()
            inbar = lambda: ctx[Bar]()
            inbaz = lambda: ctx[Baz]()
            infoobar = lambda: ctx[FooBar]()
            infoobarbaz = lambda: ctx[FooBarBaz]()
            inservice = lambda: ctx[Service]()

            print('')

            infoo(), inbar(), inbaz(), infoobar(), infoobarbaz(), inservice()
            # assert 0

            profile(mkfoo, ctx[Foo], 'Foo')
            profile(mkbar, ctx[Bar], 'Bar')
            profile(mkbaz, ctx[Baz], 'Baz')

            profile(mkfoobar, ctx[FooBar], 'FooBar')
            profile(mkfoobarbaz, ctx[FooBarBaz], 'FooBarBaz')


            profile(mkservice, ctx[Service], 'Service')

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

