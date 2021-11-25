from functools import reduce
import typing as t 

from collections.abc import Set
from djx.common.enum import Enum, StrEnum, auto, IntFlag, Flag

from djx.common.utils import export, cached_class_property


# T_HttpMethodStrLower = t.Literal['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']
# T_HttpMethodStrUpper = t.Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE']
# T_HttpMethodStr = t.Literal[T_HttpMethodStrLower, T_HttpMethodStrUpper]



@export()
class HttpMethod(Flag):

    # ANY: 'HttpMethod'       = auto()

    OPTIONS:  'HttpMethod'  = auto() #1 << 1
    HEAD:  'HttpMethod'     = auto() 
    GET:  'HttpMethod'      = HEAD | 1 << 2
    POST:  'HttpMethod'     = auto()
    PUT:  'HttpMethod'      = auto() 
    PATCH:  'HttpMethod'    = auto() 
    DELETE:  'HttpMethod'   = auto()
    TRACE:  'HttpMethod'    = auto()


    options:  'HttpMethod'  = OPTIONS
    head:  'HttpMethod'     = HEAD 
    get:  'HttpMethod'      = GET 
    post:  'HttpMethod'     = POST
    put:  'HttpMethod'      = PUT 
    patch:  'HttpMethod'    = PATCH 
    delete:  'HttpMethod'   = DELETE
    trace:  'HttpMethod'    = TRACE

    @cached_class_property
    def ALL(cls) -> 'HttpMethod':
        return ~cls.TRACE | cls.TRACE
    
    @cached_class_property
    def NONE(cls) -> 'HttpMethod':
        return cls(0)
    
    @classmethod
    def _missing_(cls, val):
        tp = val.__class__
        if tp is int:
            return super()._missing_(val)
        elif tp is str:
            mem = cls._member_map_.get(val)
            if mem is None:
                raise ValueError(f"{val!r} is not a valid {cls.__qualname__}")
            return mem
        elif issubclass(tp, Set):
            if val:
                return reduce(lambda a, b: a|cls(b), val, cls.NONE)
            return cls.NONE
        
        return super()._missing_(val)

    def __contains__(self, x) -> bool:
        if isinstance(x, str):
            x = self.__class__._member_map_.get(x, x)
        return super().__contains__(x)
        



vardump([*HttpMethod], HttpMethod['get'] == 'GET', ~HttpMethod('GET'), ~HttpMethod.GET & HttpMethod.POST)

vardump(GET=HttpMethod.GET, GET_INV=~HttpMethod.GET, ANY=~HttpMethod.GET & HttpMethod.DELETE, GET_EQ=HttpMethod['get'] == 'GET')

print('-'*80)
print('',
    f'{HttpMethod.GET & HttpMethod.HEAD=!r}', 
    f'{HttpMethod.GET in HttpMethod.HEAD=!r}', 
    f'{HttpMethod.HEAD in HttpMethod.GET=!r}', 
    sep='\n  ', end='\n\n'
)

print('-'*80)
