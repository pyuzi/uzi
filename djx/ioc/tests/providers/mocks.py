import typing as t
from dataclasses import dataclass


import pytest

from ...providers import (
    provide, injectable
)
from ... import symbol



@injectable
class Foo:
    
    @classmethod
    def cls_method(cls, arg) -> None:
        pass

    def method1(self, arg) -> None:
        pass
    
    def method2(self, arg) -> None:
        pass
    


class Bar(Foo):

    def method2(self, arg) -> None:
        ...


@injectable(context='abc')
def user_func_injectable():
    ...


user_symb = symbol('test-import')
noop_symb = symbol('noop-symbol')

def user_func_symb():
    ...


provide(user_symb, using=user_func_symb)


user_str = 'test-str'

def user_func_str():
    ...

provide(user_str, using=user_func_str)

