

from typing import Generic, MutableMapping, NoReturn, TypeVar
from flex.utils.decorators import export



from .abc import Injector


@export()
class CacheDict():
    """CacheLike Object"""

    def __init__(self, arg):
        self.arg = arg



_C = TypeVar('_C', bound=MutableMapping)



@export()
class CacheEngine(Generic[_C]):
    """Cache Object"""

    def setup(self):
        pass
        
    def load(self, inj: Injector) -> _C:
        pass

    def dump(self, data: _C, inj: Injector) -> NoReturn:
        pass
        
    
    