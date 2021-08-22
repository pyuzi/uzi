
import typing as t
from abc import ABCMeta, abstractmethod
from collections.abc import MutableMapping
from djx.common.utils import export


from djx.di import di

from ..util import django_settings



@export()
@di.injectable(di.MAIN_SCOPE, cache=True)
class Settings(metaclass=ABCMeta):
    
    __slots__ = ()
    
    DEBUG = False
    TIME_ZONE = None

    def __new__(cls) -> 'Settings':
        return django_settings() or super().__new__(cls)


settings: Settings = di.proxy(Settings, callable=True)



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




class Auth(metaclass=ABCMeta):
    """Auth Object"""

    @property
    @abstractmethod
    def user(self) -> User:
        ...

    @property
    @abstractmethod
    def authenticate_user(self) -> t.Optional[User]:
        ...

    @abstractmethod
    def authenticate(self, **credentials):
        ...
        
    @abstractmethod
    def login(self, user: User, backend: str=None):
        ...

    @abstractmethod
    def logout(self):
        ...
