from enum import Enum

from collections import UserString
from typing import ClassVar, Type, get_type_hints

from flex.utils.decorators import class_property, export


class _HttpMethodBase(str):
    __slots__ = ()

    @property
    def altcase(self) -> str:
        return self.upper()

    # def __eq__(self, x):
    #     return super().__eq__(x) or self.altcase == x
    
    # def __ne__(self, x):
    #     return not self.__eq__(x) 

    # @classmethod
    # def __get__(cls, type) -> None:
    #     pass
    
    






@export()
class HttpMethod(_HttpMethodBase, Enum):

    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT' 
    PATCH = 'PATCH' 
    DELETE = 'DELETE'
    HEAD = 'HEAD' 
    OPTIONS = 'OPTIONS'
    TRACE = 'TRACE'
  
    @property
    def altcase(self):
        return self.lower()

    def Lower(cls):
        return Enum(
            'HttpMethodLower', 
            names=((k.upper(), k) for k in ['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']),
            type=_HttpMethodBase,
            qualname='HttpMethod.HttpMethodLower'
        )

    Lower: Type['HttpMethod.Lower'] = class_property(Lower)


