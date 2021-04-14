import typing as t
from dataclasses import dataclass


import pytest

from djx.ioc.symbols import StaticIndentity, SupportsIndentity



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




def user_func():
    ...


@StaticIndentity.register
@dataclass(frozen=True)
class UserStaticIdentity:
    val: str
    opt: t.Any = None





@SupportsIndentity.register
@dataclass(frozen=True)
class UserIdentitySupport:
    val: int
    opt: t.Any = None


supported_obj = UserIdentitySupport(1)




@dataclass(frozen=True)
class NotSupported:
    val: int = 123
    opt: t.Any = None


