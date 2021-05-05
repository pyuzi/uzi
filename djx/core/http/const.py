from enum import Enum

from flex.utils.decorators import export





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
  
    def __eq__(self, x) -> bool:
        return super().__eq__(x.upper() if isinstance(x, str) else x)

    def __ne__(self, x) -> bool:
        return super().__ne__(x.upper() if isinstance(x, str) else x)
