
import typing as t
from abc import ABCMeta, abstractmethod
from collections.abc import MutableMapping, Mapping
from djx.common.utils import export


from djx.di import ioc

from ..util import django_settings



@export()
@ioc.injectable(at='main', cache=True)
class Settings(metaclass=ABCMeta):
    
    __slots__ = ()
    
    DEBUG = False
    TIME_ZONE = None

    def __new__(cls) -> 'Settings':
        return django_settings() or super().__new__(cls)


settings: Settings = ioc.proxy(Settings, callable=True)



@ioc.injectable(at='request')
class Request(metaclass=ABCMeta):
    __slots__ = ()

    session: 'Session'
    user: 'User'





@export()
class Response(metaclass=ABCMeta):
    __slots__ = ()




@export()
@ioc.injectable(at='request')
class Session(MutableMapping):
    __slots__ = ()




@export()
@ioc.injectable(at='request')
class User(metaclass=ABCMeta):
    __slots__ = ()

    id: t.Any
    username: str

    is_active: bool
    is_authenticated: bool



_T_Rendered = t.TypeVar('_T_Rendered')
@export()
class Renderable(t.Generic[_T_Rendered], metaclass=ABCMeta):

    __slots__ = ()

    @classmethod
    def __subclasshook__(cls, klass: type) -> bool:
        if cls is Renderable:
            return hasattr(klass, 'render') and callable(klass, 'render')
        return NotImplemented

    @abstractmethod
    def render(self, *args, **kwds) -> _T_Rendered:
        ...




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
