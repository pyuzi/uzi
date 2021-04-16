
from collections.abc import Mapping, MutableMapping
from types import FunctionType
from contextvars import ContextVar
from typing import Any, Callable, ClassVar, Generic, Optional, Sequence, Type, TypeVar, Union


from flex.utils.decorators import export


from .exc import ProviderNotFoundError
from .providers import ProviderStack, Provider
from .symbols import symbol
from . import abc


_T_Conf = TypeVar('_T_Conf')


@export
class ContextType(abc.ABCMeta):
    

    def __new__(mcls, name, bases, dct):

        # raw_conf = dct.get('Config')
                
        # meta_use_cls = raw_conf and getattr(raw_conf, '__use_class__', None)
        # meta_use_cls and dct.update(__config_class__=meta_use_cls)

        cls = super().__new__(mcls, name, bases, dct)

        # conf_cls = get_metadata_class(cls, '__config_class__')
        # conf_cls(cls, '_conf', raw_conf)

        return cls






@export
@abc.Context.register
class Context(Generic[_T_Conf], metaclass=ContextType):
    """"""
    __slots__ = ()

    name: str

    label: str

    providers: ProviderStack

    # caches: dict[str, Callable[..., MutableMapping]]

    depends: Sequence[str]

    config: _T_Conf

    # def __init__(self, name: str, providers: ProviderStack, **options) -> None:
    #     self.name
    #     self.providers
    #     self.config = options

    def create_cache(self, ) -> None:
        pass

    def setup(self) -> None:
        pass

    def setup_providers(self):
        pass

    def call(self, cb: Callable, args: tuple, kwds: dict) -> 'Injector':
        pass

    def open(self) -> None:
        pass
    
    def close(self) -> None:
        pass
    
    def __enter__(self) -> 'Context':
        self.open()
        return self
    
    def __exit__(self, *exc) -> None:
        self.close()
        
    


 
    
"""
Internal Contexts
"""

MAIN = 'main'
LOCAL = 'local'
ANY = 'any'
    


def setup():
    pass




def use(ctx):
    pass


def run(cd, ctx,  _cb: Callable, /, *args) -> Any:
    with use(ctx) as ctx:
        return _cb(*args)





class ContextManager:
    """"""
    # __slots__ = ()
    context: Context







@export()
class Injector(Mapping[_I, _T]):

    id: int

    name: str

    context: Context

    parent: Optional['Injector'] = None

    container: ProviderStack

    cache: MutableMapping[_I, _T]

    def __init__(self, context: Context, caches: Mapping[str, MutableMapping[]], parent: Optional['Injector']=None):
        self.context = context
        self.parent = parent
        self.cache = dict()

        if parent:
            self.container = parent.container
        else:
            self.container = ProviderStack()

    @property
    def name(self):
        return self.context.name

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
        return len(self.cache)
  
    def __iter__(self):
        return iter(self.cache)

    def __getitem__(self, k: _I) -> _I:
        if isinstance(k, list):
            return [self[d] for d in k]
        elif not isinstance(k, Provider):
            p = self.get_provider(k)
        else:
            p = k

        if p.cache:
            rv = self.cache.get(p, ...)
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