
import typing as t
from abc import ABCMeta, abstractmethod
from jani.common.utils import export


from jani.di import ioc






@export()
@ioc.injectable(at='request')
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
