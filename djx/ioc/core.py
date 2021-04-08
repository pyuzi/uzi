
from collections import defaultdict
from email.policy import strict
import gc
import inspect

from inspect import Signature, Parameter, signature
from types import FunctionType, LambdaType, MethodType
from typing import Any, Callable, ClassVar, ContextManager, Generator, Generic, List, Mapping, MutableMapping, NoReturn, Optional, Type, TypeVar, Union, final
from contextlib import contextmanager
from weakref import WeakKeyDictionary, ref


from flex.utils.decorators import export


from .exc import ProviderNotFoundError
from .symbols import Symbol


__all__ = [

]

_TD = TypeVar('_TD')

ProvidedType = TypeVar('ProvidedType')

FuncProviderType = TypeVar("FuncProviderType", bound=Callable[..., Any])

InjectableType = Union[Symbol, Type, FunctionType]


_I = TypeVar('_I', bound=InjectableType)
_T = TypeVar('_T')


class DependencySignature(Signature):
    __slots__ = ('_deps',)



@export()
class Resolver(Generic[_T]):

    __slots__ = ('_')
    priority: int = 0

    symbol: Symbol

    shared: bool = False

    dependencies: Mapping[str, _I]

    def __init__(self, symbol: Symbol, /, priority: int=None) -> None:
        self.symbol = symbol
        self.priority = self.priority if priority is None else priority
    
    def deconstruct(self, injetor):
        raise NotImplementedError(f'{type(self)}.deconstruct()')

    def resolve(self, injetor: 'Injector', abstract) -> _T:
        raise NotImplementedError(f'{type(self)}.deconstruct()')



@export()
class ContextProvider(Resolver[_T]):
    """FunctionProvider Object"""

    func: Callable[...,Generator[ProvidedType, Optional[Any], Optional[Any]]]




@export()
class FunctionResolver(Resolver[_T]):
    """FunctionProvider Object"""

    func: FunctionType

    def __init__(self, func: FunctionType, priority: int=None):
        if isinstance(func, LambdaType):
            raise ValueError(f'LambdaTypes are not resolvable.')
        self.func = func
        super().__init__(priority=priority)


    def deconstruct(self, injetor):
        sig = signature(self.func)
        for n ,p in sig.parameters.items():
            if self.is_injectable(p):
                pass





@export()
class ClassResolver(FunctionResolver):
    """ClassResolver Object"""
    pass


@export()
class MethodResolver(FunctionResolver):
    """MethodResolver Object"""
    pass

@export()
class ValueResolver(Resolver):
    """ValueResolver Object"""
    pass


_missing = object()

class _ResolverMap(WeakKeyDictionary, Mapping[_I, List[Resolver[_T]]]):

    def __init__(self) -> None:
        self.data = WeakKeyDictionary()   

    def head(self, k, default=None) -> Optional[Resolver[_T]]:
        return self.data.get(k, (default,))[-1]
    
    def setdefault(self, k, val: Resolver[_T]) -> Resolver[_T]:
        return self.data.setdefault(k, [val])[-1]
    
    def push(self, k, resolver: Resolver[_T]) -> Resolver[_T]:
        stack: List[Resolver] = self.data.setdefault(k, [])
        i = len(stack) - 1
        while i > 0:
            if stack[i].priority <= resolver.priority:
                break
            i -= 1
        
        stack.insert(i+1, resolver)
        return resolver

    


@export()
class Injector(Mapping[_I, _T]):

    resolvers: _ResolverMap

    resolved: Mapping[_I, _T]

    resolved: MutableMapping[_I, _T]

    def __init__(self):
        self.resolvers = _ResolverMap()
        self.resolved = dict()
    
    def get(self, k: _I, default=None) -> _I:
        try:
            return self[k]
        except KeyError:
            return default
    
    def __len__(self) -> int:
        return len(self.resolved)
  
    def __iter__(self):
        return iter(self.resolved)

    def __getitem__(self, k: _I) -> _I:
        s = Symbol(k)
        try:
            return self.resolved[s]
        except KeyError:
            res = self.get_resolver(k)
            if res.shared:
                return self.resolved.setdefault(s, res.resolve(self, k))
            else:
                return res.resolve(self, k)
    
    def get_resolver(self, k: _I) -> Resolver[_T]:

        s = Symbol(k)
        if rv := self.resolvers.head(s):
            return rv

        if isinstance(k, type):
            return self.resolvers.push(s, ClassResolver(s, -1))
        elif isinstance(k, MethodType):
            return self.resolvers.push(s, MethodResolver(s, -1))
        elif isinstance(k, FunctionType):
            return self.resolvers.push(s, FunctionResolver(s, -1))
            
        raise ProviderNotFoundError(s)


        



inj = Injector()

# inj['ABCD']
    

print(f'{Injector.get.__self__=}, {isinstance(Injector.get, FunctionType)=}, {inspect.ismethod(Injector.get)=}',)
# 
print(Injector.get, Injector.get.__closure__, sep='\n - ', end='\n\n')



print(f'{inj.get=}', f'{inj.get.__self__=}',  f'{inj.get.__func__=}', f'{inj.get.__func__ is Injector.get=}', sep='\n - ', end='\n\n')