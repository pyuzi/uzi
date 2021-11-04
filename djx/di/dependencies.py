import typing as t
from djx.common.abc import Orderable 


from djx.common.utils import export, cached_property
from djx.common.saferef import saferef
from djx.di import providers
from djx.di.inspect import ordered_id

from . import abc
from .abc import T_Injectable, T_Injected    

if t.TYPE_CHECKING:
    from . import IocContainer, Provider as DependencyRef

@export()
class KindOfProvider():
    alias       = 1
    value       = 2
    func        = 3
    type        = 4
    provider    = 5




@export()
@abc.Dependency.register
class Dependency(t.Generic[T_Injected, T_Injectable]):

    abstract: T_Injectable

    def __init__(self, 
                concrete,
                *,
                priority: t.Optional[int]=1,
                scope: str = None, 
                cache: bool=None, 
                **kwds) -> None:
        self.__pos = ordered_id()

        self.concrete = saferef(concrete)
        self.scope = scope # or self._default_scope
        self.cache = cache
        self.priority = priority or 0

        setattr = object.__setattr__
        for k,v in kwds.items():
            if k[0] == '_' or k[-1] == '_':
                raise AttributeError(f'invalid attribute {k!r}')
            
            setattr(self, k, v)
        
    @property
    def abstract(self):
        return self.abstract_ref()

    @property
    def type(self):
        return self.type

    def __eq__(self, x) -> bool:
        if isinstance(x, abc.Dependency):
            return self.abstract.__eq__(x.abstract)
        return False

    # def __hash__(self) -> int:
    #     return hash((abc.Dependency, self.abstract))
    
    def __repr__(self):
        return f'{self.__class__.__name__}({self.abstract}, {self.concrete}, {self.scope})'

    def __order__(self):
        return (self.priority, self.__pos, self.abstract)
        
    __gt__ = Orderable.__gt__
    __ge__ = Orderable.__ge__
    __lt__ = Orderable.__lt__
    __le__ = Orderable.__le__

    def __call__(self, ioc: 'IocContainer', abstract: T_Injectable) -> 'DependencyRef[T_Injected]':
        pass
    