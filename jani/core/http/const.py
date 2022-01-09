import typing as t

from jani.common.enum import Enum

from jani.common.utils import export





@export()
class HttpMethod(str, Enum):

    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT' 
    PATCH = 'PATCH' 
    DELETE = 'DELETE'
    HEAD = 'HEAD' 
    OPTIONS = 'OPTIONS'
    TRACE = 'TRACE'

    def _missing_(cls, val):
        if isinstance(val, str):
            return cls._create_pseudo_member_(val)

    @classmethod
    def _create_pseudo_member_(cls, value: str):
        """
        Create a composite member iff value contains only members.
        """
        pseudo = cls._value2member_map_.get(value, None)
        if pseudo is None and value.islower():
            real = cls(value.upper())

            pseudo = str.__new__(cls, real._value_)
            pseudo._name_ = None
            pseudo._value_ = value

            pseudo = cls._value2member_map_.setdefault(value, pseudo)

        return pseudo

    def __eq__(self, x) -> bool:
        return super().__eq__(x.upper() if isinstance(x, str) else x)

    def __ne__(self, x) -> bool:
        return super().__ne__(x.upper() if isinstance(x, str) else x)
