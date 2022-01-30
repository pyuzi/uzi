from pprint import pprint
from types import GenericAlias
import typing as t
import inspect as ins
import pytest
from functools import wraps

from laza.di import new_providers as p
from laza.di.new_container import IocContainer
from laza.di.new_scopes import MainScope, LocalScope





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
        con2.type(Baz, Baz)

        con3 = IocContainer(con1, con2) 
        con3.type(FooBar, FooBar)
        con3.type(FooBarBaz, FooBarBaz)

        con4 = IocContainer(con2)


        scope1 = MainScope(con3)
        scope2 = LocalScope(scope1)
        scope3 = LocalScope(scope2, con4)

        with scope2.create_injector() as inj_:
            with scope3.create_injector(inj_) as inj:
                print(f'---> {inj=}')
                print(f'---> {inj.scope._context.get()!r}')
                print(inj[Foo])
                print(inj[FooBarBaz])

                assert isinstance(inj[Foo], Foo)
                assert isinstance(inj[Baz], Baz)
                assert inj[Foo] is not inj[Foo]


                
        assert 0, '\n'
 
   


class Foo:
    ...
    
class Bar:
    ...
     
class Baz:
    ...
    
 
class FooBar(Foo, Bar):
    ...
     

class FooBarBaz(FooBar, Baz):
    ...
    