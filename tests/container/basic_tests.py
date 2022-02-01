from pprint import pprint
from types import GenericAlias
import typing as t
import inspect as ins
import pytest
from functools import wraps

from laza.di import Injector, InjectionToken
from laza.di.container import Container
from laza.di.scopes import Scope, MainScope




xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize






class BasicScopeTests:

 
    def test_basic(self):
        con1 = Container() 
        con2 = Container() 
        con3 = Container(con1, con2) 
        con4 = Container(con3)

        scope1 = MainScope(con2, con1)
        scope2 = Scope('scope2', scope1, con4)


        print(scope2) 
        pprint([*scope2.dependencies]) 
        pprint([*scope2.local_dependencies]) 
        pprint([*scope2.registry]) 

        assert 0, '\n'

 
    def test_providers(self):
        con1 = Container() 

        con1.type(Foo, Foo)
        con1.type(Bar, Bar)
        
        con2 = Container(shared=False) 
        con2.type(Baz, Baz)

        con3 = Container(con1, con2) 
        con3.type(FooBar, FooBar)
        con3.type(FooBarBaz, FooBarBaz)

        con4 = Container(con2)


        scope1 = MainScope(con3)
        scope2 = Scope('scope2', scope1, con4)

        inj = scope2.create(None)
        print(inj[Foo])
        print(inj[FooBarBaz])

        assert isinstance(inj[Foo], Foo)
        assert isinstance(inj[Baz], Baz)
        assert inj[Foo] is not inj[Foo]
       
        assert 1, '\n'
 
   


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
    