from typing_extensions import Literal
import typing as t
import inspect as ins
import pytest
from typing import Optional, Union

from ...inspect import  BoundArguments, signature, InjectableSignature, Parameter


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


class Foo:

    
    @classmethod
    def cls_method(cls, arg) -> None:
        pass

    def method1(self, arg) -> None:
        pass
    
    def method2(self, arg) -> None:
        pass
    
class Bar(Foo):

    __injectable__ = True

    def method2(self, arg) -> None:
        pass


class Baz(Bar):

    def __init__(self, arg) -> None:
        pass
    



def foo(a: Foo, 
        b: Optional['Bar'], 
        c: Union[Baz, tuple, list], 
        o: Optional[dict]=None, 
        d: Bar = None):
    pass



class SignatureTests:

    def test_basic(self):
        sig = signature(foo)
        print(f'{sig=!r}')
        assert isinstance(sig, InjectableSignature)
        # assert sig is signature(foo) is signature(foo)

        for n, p in sig.parameters.items():
            assert isinstance(p, Parameter)
            print(f'{n.rjust(16)} --> {p!r}')

        args = sig.bind_partial()
        assert isinstance(args, BoundArguments)

        assert isinstance(sig.bound(), BoundArguments)

        assert isinstance(sig._bound, BoundArguments) 
        assert sig._bound is sig._bound

        assert 1, '\n'
 


            
        
    