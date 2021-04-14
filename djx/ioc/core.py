
from collections.abc import Mapping, MutableMapping
from djx.ioc.exc import ProviderNotFoundError
from types import FunctionType
from typing import Optional, Type, TypeVar, Union


from flex.utils.decorators import export


from .providers import Container, Provider
from .symbols import symbol




InjectableType = Union[symbol, Type, FunctionType]


_I = TypeVar('_I', bound=InjectableType)
_T = TypeVar('_T')





@export()
class Injector(Mapping[_I, _T]):

    container: Container

    cached: MutableMapping[_I, _T]

    name: str

    parent: Optional['Injector'] = None

    def __init__(self, name: str, parent: Optional['Injector']=None):
        self.name = name
        self.parent = parent
        self.cached = dict()

        if parent:
            self.container = parent.container
        else:
            self.container = Container()

    @property
    def root(self):
        return self if self.parent is None else self.parent.root

    def ancestors(self, inc_self=True):
        if inc_self:
            yield self

        p = self.parent
        while p is not None:
            yield p
            p = p.parent

    def setup_context(self) -> Mapping:
        return {}
    
    def get(self, k: _I, default=None) -> _I:
        try:
            return self[k]
        except KeyError:
            return default
    
    def __bool__(self):
        return True
  
    def __len__(self) -> int:
        return len(self.cached)
  
    def __iter__(self):
        return iter(self.cached)

    def __getitem__(self, k: _I) -> _I:
        if isinstance(k, list):
            return [self[d] for d in k]
        elif not isinstance(k, Provider):
            p = self.get_provider(k)
        else:
            p = k

        if p.is_cached:
            rv = self.cached.get(p, ...)
            if rv is ...:
                return self.parent[p] if self.parent else None
            
            # for a in self.ancestors():
            #     if a.name in p.contexts:
            #         self = a
            #         break
            # else:
            #     raise LookupError(f'Context not found: {p.contexts}')

        return p.provide(self, __self__=getattr(k, '__self__', None))
    
    def __enter__(self):
        return self

    def __exit__(self, *exec):
        pass
    
    def __call__(self, name):
        return self.__class__(name, self)
    
    def bind(self, arg) -> None:
        pass
    
    def create(self, scope):
        pass

    def get_provider(self, k: _I, *, create=True) -> Provider[_T]:
        if rv := self.container.get(s := symbol(k), recursive=True):
            return rv
        elif create and callable(v := s()):
            return self.container.bind(s, v, -10)
        else:
            raise ProviderNotFoundError(s)
        




inj = Injector()

# inj['ABCD']
    

print(f'{Injector.get.__self__=}, {isinstance(Injector.get, FunctionType)=}, {inspect.ismethod(Injector.get)=}',)
# 
print(Injector.get, Injector.get.__closure__, sep='\n - ', end='\n\n')



print(f'{inj.get=}', f'{inj.get.__self__=}',  f'{inj.get.__func__=}', f'{inj.get.__func__ is Injector.get=}', sep='\n - ', end='\n\n')