from pprint import pprint
from types import GenericAlias
import typing as t
import inspect as ins
import pytest
from functools import wraps

from laza.di.containers import IocContainer
from laza.di.scopes import MainScope, LocalScope





xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize






class BasicScopeTests:

 
    def test_basic(self):
        con1 = IocContainer() 
        con2 = IocContainer() 
        con3 = IocContainer(con1, con2) 
        con4 = IocContainer(con3)

        scope1 = MainScope(con2, con1)
        scope2 = LocalScope(scope1, con4)


        print(scope2) 
        pprint([*scope2.requires]) 
        pprint([*scope2.repository]) 
        pprint([*scope2.registry]) 

        assert 1, '\n'

 
    def test_providers(self):
        con1 = IocContainer() 

        con1.type(Foo)
        # con1[Foo] = p.Type(Foo)

        con1.type(Bar)
         
        con2 = IocContainer(shared=False) 
        con2.type(Baz)

        con3 = IocContainer(con1, con2) 
        con3.type(FooBar, FooBar)
        con3.type(FooBarBaz, FooBarBaz)

        con4 = IocContainer(con2)


        scope1 = MainScope(con3)
        scope2 = LocalScope(scope1)
        scope3 = LocalScope(scope2, con4)

        with scope2.make() as inj_:
            with scope3.make(inj_) as inj:
                print(f'---> {inj=}')
                print(f'---> {inj.scope._context.get()!r}')
                print(inj[Foo])
                print(inj[FooBarBaz])

                assert isinstance(inj[Foo], Foo)
                assert isinstance(inj[Baz], Baz)
                assert inj[Foo] is not inj[Foo]

        assert 1, '\n'
 
    def test_inject(self):
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


        scope1 = MainScope(con3)
        scope2 = LocalScope(scope1)
        scope3 = LocalScope(scope2, con4)

        with scope2.make() as inj_:
            with scope3.make(inj_) as inj:
                print(f'---> {inj=}')
                print(f'---> {inj.scope._context.get()!r}')
                # print(inj[Foo])
                print(f'{inject_con4()=}')

                assert all(isinstance(o, c) for o,c in zip(inject_con4(), (Baz, Foo)))
               
        assert 1, '\n'
 
    def test_perfomance(self, speed_profiler):
        ioc = MainScope() 

        ioc.type(Foo, shared=False)
        ioc.type(Bar, shared=True)
        ioc.type(Baz, shared=True)


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

        _n = int(1e5)
        profile = speed_profiler(_n, labels=('PY', 'DI'))
        xprofile = speed_profiler(_n, labels=('DI', 'PY'))


        with ioc.make() as inj:

            infoo = lambda: inj[Foo]
            inbar = lambda: inj[Bar]
            inbaz = lambda: inj[Baz]

            profile(mkfoo, infoo, 'Foo')
            profile(mkbar, inbar, 'Bar')
            profile(mkbaz, inbaz, 'Baz')

            profile(mkinject_1, inject_1, inject_1.__name__)
            profile(mkinject_2, inject_2, inject_2.__name__)

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
    