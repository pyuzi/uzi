from typing_extensions import Literal
import typing as t
import inspect as ins
import pytest
from typing import Optional, Union

from djx.ioc.inspect import Depends, InjectableBoundArguments, signature, InjectableSignature, InjectableParameter
from djx.ioc.symbols import symbol


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
    



def foo(a: Depends(Foo, symbol(Foo)), 
        b: Optional['Bar'], 
        c: Union[Baz, tuple, list], 
        o: Optional[dict]=None, 
        d: Depends[Foo, symbol('raw.bar'), Bar] = None):
    pass


class SignatureTests:

    def test_basic(self):
        sig = signature(foo)
        assert isinstance(sig, InjectableSignature)

        print(f'{sig=!r}')

        for n, p in sig.parameters.items():
            assert isinstance(p, InjectableParameter)
            print(f'  {n.rjust(20)} --> {p!r}')

        args = sig.bind_partial()
        assert isinstance(args, InjectableBoundArguments)


        assert signature(foo) is sig

        assert 0, '\n'