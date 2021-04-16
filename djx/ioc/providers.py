
from collections import defaultdict
from collections.abc import Sequence

from weakref import WeakSet

from types import FunctionType, MethodType
from typing import Any, Callable, ClassVar, Generic, Optional, Type, TypeVar, Union, overload


from flex.utils.decorators import export


from .symbols import symbol, _ordered_id
from . import abc, registry

__all__ = [

]


_T = TypeVar('_T')
_I = TypeVar('_I', bound=abc.Injectable)
_P = TypeVar('_P', bound='Provider')


_provided = WeakSet()

def has_provider(obj) -> bool:
    return isinstance(obj, abc.SupportsIndentity) and symbol(obj) in _provided



@export()
def alias(abstract: _I, 
        alias: abc.Injectable[_T], 
        priority: int = 1, *, 
        context: Optional[str] = None, 
        **opts) -> 'AliasProvider':
    """Registers an `AliasProvider`
    """
    return provide(abstract, priority, alias=alias, context=context, **opts)
        


@export()
def injectable(concrete: Callable[..., _T]=None, /,
        priority: int = 1, *, 
        context: Optional[str] = None, 
        abstract: _I = None,
        **opts):

    def register(using):
        provide(abstract or using, priority, using=using, context=context, **opts)
        return using
    return register if concrete is None else register(concrete)
     



_kwd_cls_map = dict(
    using=lambda: FactoryProvider, 
    alias=lambda: AliasProvider, 
    value=lambda: ValueProvider
)

@overload
def provide(abstract: _I, priority: int = 1, /, *, value: _T, context: str = None, **opts) -> 'ValueProvider': ...
@overload
def provide(abstract: _I, priority: int = 1, /, *, alias: abc.Injectable[_T], context: str = None, **opts) -> 'AliasProvider': ...
@overload
def provide(abstract: _I, priority: int = 1, /, *, using: Callable[..., _T],
        context: str = None, cache: Union[str, bool] = False, **opts) -> 'FactoryProvider': 
        ...
@export()
def provide(abstract: _I, priority: int = 1, /, *, 
        using: Callable[..., _T] = ..., alias: abc.Injectable[_T]=..., value: _T=...,
        cache: Optional[Union[str, bool]] = None, context: Optional[str] = None, 
        **opts) -> 'Provider':
    var = vars()
    concrete = next((c for c in _kwd_cls_map if var[c] is not ...))
    cls = _kwd_cls_map[concrete]()
    return register_provider(cls(abstract, var[concrete], priority, cache=cache, context=context, **opts))
        





@export()
def register_provider(provider: _P, context: str = None) -> _P:
    return registry.add_provider(provider, context)






@export()
@abc.SupportsIndentity.register
@abc.CanSetupContext.register
class Provider(Generic[_I, _T]):

    __slots__ = (
        'abstract', 'concrete', 'context', '__pos',
        'cache', 'priority', 'options', '__weakref__',
    )

    _default_context: ClassVar[str] = 'main'
    
    abstract: symbol[_I]

    context: Optional[str]
    priority: int
    concrete: Any
    cache: bool
    options: dict
    __pos: int

    def __init__(self, 
                abstract: _I,   
                concrete: Any, 
                priority: Optional[int]=1, *,
                context: Optional[str] = None, 
                cache: Union[bool, str]=False, 
                **options) -> None:
        global _provided

        self.abstract = symbol(abstract)
        self.__pos = _ordered_id()
        self.context = context or self._default_context
        self.cache = cache
        self.priority = priority or 0
        self.options = options
        self.set_concrete(concrete)
        _provided.add(self.abstract)

    def set_concrete(self, concrete) -> None:
        self.concrete = concrete
    
    def check(self):
        assert isinstance(self.abstract, symbol), '`abstract` must be a `symbpl`'

    def setup(self, context: abc.Context) -> None:
        pass

    def provide(self, inj: abc.Injector, *args, **kwds) -> _T:
        return self.concrete
#
    def __ge__(self, x) -> bool:
        if isinstance(x, Provider):
            return self.priority > x.priority\
                or self.priority == x.priority\
                    and self.__pos >= x.__pos
        return NotImplemented

    def __gt__(self, x) -> bool:
        if isinstance(x, Provider):
            return self.priority > x.priority\
                or self.priority == x.priority\
                    and self.__pos > x.__pos

        return NotImplemented

    def __le__(self, x) -> bool:
        if isinstance(x, Provider):
            return self.priority < x.priority\
                or self.priority == x.priority\
                    and self.__pos <= x.__pos
        return NotImplemented

    def __lt__(self, x) -> bool:
        if isinstance(x, Provider):
            return self.priority < x.priority\
                or self.priority == x.priority\
                    and self.__pos < x.__pos
        return NotImplemented

    def __eq__(self, x) -> bool:
        if isinstance(x, Provider):
            return self.abstract == x.abstract\
                and self.context == x.context\
                and self.priority == x.priority\

        return NotImplemented

    # def __hash__(self, x) -> bool:
    #     return hash((self.__class__, self.context, self.abstract, self.concrete))
    

@export()
class ValueProvider(Provider):

    __slots__ = ()
    concrete: _T

    def provide(self, inj: abc.Injector, *args, **kwds) -> _T:
        return self.concrete



@export()
class AliasProvider(Provider):

    __slots__ = ()
    concrete: symbol[_T]

    def check(self):
        super().check()
        assert has_provider(self.concrete), (
                f'No provider for aliased `{self.concrete}` in `{self.abstract}`'
            )

    def set_concrete(self, concrete) -> None:
        self.concrete = symbol(concrete)
    
    def provide(self, inj: abc.Injector, *args, **kwds) -> _T:
        return inj[self.concrete]




@export()
class FactoryProvider(Provider):

    __slots__ = ('_sig')
    concrete: symbol[Callable[..., _T]]

    @property
    def factory(self):
        return self.concrete()

    @property
    def signature(self):
        if rv := getattr(self, '_sig', None):
            return rv
        
        from .inspect import signature
        self._sig = signature(self.factory)
        return self._sig

    def check(self):
        super().check()
        assert callable(self.factory), (
                f'`concrete` must be a valid Callable. Got: {type(self.factory)}'
            )

    def set_concrete(self, concrete) -> None:
        self.concrete = symbol(concrete)
    
    def bind(self, injector: abc.Injector, *args, **kwds):
        return self.signature.inject(injector, *args, **kwds)

    def provide(self, injector: abc.Injector, *args, **kwds):
        params = self.bind(injector, *args, **kwds)
        return self.factory(*params.args, **params.kwargs)


class ProviderStack(dict[symbol[_I], list[_P]]):
    
    __slots__= ()

    def push(self, provider: _P) -> _P:
        stack = super().setdefault(provider.abstract, [])
        stack.append(provider)
        stack.sort()
        return provider

    @overload
    def pop(self, provider: _P, default=...):...
    @overload
    def pop(self, key: symbol[_I], default=...):...
    def pop(self, k, default=...):
        provider = None
        if isinstance(k, Provider): 
            provider = k
            k = k.abstract
            
        try:
            if provider is None:
                return super().pop(k)
            else:
                self[k].remove(provider)
        except KeyError:
            if default is ...:
                raise
            return default
        else:
            return provider

    def setdefault(self, provider, val: _P = ...) -> _P:
        if isinstance(val, Provider):
            provider = val

        stack = super().setdefault(provider.abstract, [])
        stack or stack.append(provider)
        return stack[-1]

    @overload
    def __getitem__(self, k: slice) -> list[_P]: ...
    @overload
    def __getitem__(self, k: Any) -> _P: ...
    def __getitem__(self, k) -> _P:
        if isinstance(k, slice):
            return self[k.start]
        else:
            return self[symbol(k)][-1]

            

