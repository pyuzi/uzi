from dataclasses import KW_ONLY, InitVar, dataclass, field
from types import GenericAlias

import typing as t

from collections.abc import Callable

from laza.common.functools import export



from .common import T_Injectable, T_Injected, ScopeVar

if t.TYPE_CHECKING:
    from .scopes import Scope
    from .providers_new import Provider


@export()
class ResolverFunc(t.Callable[['Injector'], T_Injected], t.Generic[T_Injected]):
    ...
    # @abstractmethod
    # def __call__(self, injector: 'Injector') -> t.Union['InjectorVar[T_Injected]', None]:
    #     ...

    # @classmethod
    # def __subclasshook__(cls, sub):
    #     if cls is ResolverFunc:
    #         try:
    #             return issubclass(sub, (FunctionType, MethodType, type)) or callable(getattr(sub, '__call__'))
    #         except AttributeError:
    #             pass
            
    #     return NotImplemented
    
    __class_getitem__ = classmethod(GenericAlias)




@export()
@dataclass(slots=True, frozen=True)
class Resolver:

    key: T_Injectable
    src: 'Provider'
    uses: t.Any
    deps: set[T_Injectable] = None

    use: InitVar[t.Any] = None
    factory: InitVar[t.Any] = None
    value: InitVar[t.Any] = None



    def __init__(self, 
                key: T_Injectable, 
                src: 'Provider', 
                *, 
                value: t.Any=None, 
                factory: t.Any=None, 
                using: Callable[['Scope'], 'Resolver']=None, 
                deps: set[T_Injectable]=None) -> None:
        self.key = key
        self.src = src
        self.deps = frozenset(deps or ())
        
        

    def __post_init__(self, use=...):
        self.deps = frozenset(self.deps or ())

    def __bool__(self):
        return self.use is not None

    def __call__(self, inj: 'Scope') -> ScopeVar:
        return self.use(inj)
    


@export()
@dataclass(slots=True, frozen=True)
class FuncResolver(Resolver):

    def __call__(self, inj: 'Scope') -> ScopeVar:
        fn = self.use(inj)
        if fn is not None:
            return ScopeVar(make=fn, shared=self.src.shared)
        
    
