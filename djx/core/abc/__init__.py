
import typing as t
from abc import ABCMeta
from collections.abc import MutableMapping
from djx.common.utils import export


from djx.di import di

@export()
@di.injectable(di.REQUEST_SCOPE)
class Request(metaclass=ABCMeta):
    __slots__ = ()

    session: 'Session'
    user: 'User'





@export()
class Response(metaclass=ABCMeta):
    __slots__ = ()




@export()
@di.injectable(di.REQUEST_SCOPE)
class Session(MutableMapping):
    __slots__ = ()




@export()
@di.injectable(di.REQUEST_SCOPE)
class User(metaclass=ABCMeta):
    __slots__ = ()

    id: t.Any
    username: str

    is_active: bool
    is_authenticated: bool

