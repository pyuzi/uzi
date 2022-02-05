from functools import lru_cache
from logging import getLogger
from threading import Lock
import typing as t



from threading import Lock

from collections.abc import Mapping
from laza.common.collections import Arguments, frozendict

from laza.common.functools import export, Missing



from collections.abc import Callable

from types import GenericAlias



from .typing import get_origin

from .common import Injectable, T_Injected

logger = getLogger(__name__)










@export()
class ScopeVar(t.Generic[T_Injected]):
    """Resolver t.Generic[T_InjectedObject"""

    __slots__ = ()

    value: T_Injected = Missing

    def get(self) -> T_Injected:
        ...
        
    def make(self, *a, **kw) -> T_Injected:
        ...
        
    def __new__(cls, *args, **kwds):
        if cls is ScopeVar:
            return _LegacyScopeVar(*args, **kwds)
        else:
            return object.__new__(cls)
        




@export()
class ValueScopeVar(ScopeVar[T_Injected]):
    """Resolver t.Generic[T_InjectedObject"""

    __slots__ = 'value',

    def __new__(cls, value: T_Injected):
        self = object.__new__(cls)
        self.value = value
    
        return self

    def get(self) -> T_Injected:
        return self.value

    def make(self) -> T_Injected:
        return self.value

    def __repr__(self) -> str: 
        value = self.value
        return f'{self.__class__.__name__}({value=!r})'



@export()
class FactoryScopeVar(ScopeVar[T_Injected]):
    """Factory InjectorVar"""

    __slots__ = 'make', 'get',

    def __new__(cls, make: T_Injected):
        self = object.__new__(cls)
        self.make = self.get = make
        return self
    
    def __repr__(self) -> str: 
        make = self.make
        return f'{self.__class__.__name__}({make=!r})'




@export()
class SingletonScopeVar(ScopeVar[T_Injected]):
    """Factory InjectorVar"""

    __slots__ = 'make', 'value', 'lock',

    def __new__(cls, make: T_Injected):
        self = object.__new__(cls)
        self.make = make
        self.value = Missing
        self.lock = Lock()
        return self

    def get(self) -> T_Injected:
        if self.value is Missing:
            with self.lock:
                if self.value is Missing:
                    self.value = self.make()
        return self.value
        
    def __repr__(self) -> str: 
        make, value = self.make, self.value
        return f'{self.__class__.__name__}({value=!r}, {make=!r})'



@export()
class LruCachedScopeVar(ScopeVar[T_Injected]):
    """Factory InjectorVar"""

    __slots__ = 'make', 'get',

    def __new__(cls, make: T_Injected, *, maxsize: bool=128, typed: bool=False):
        self = object.__new__(cls)
        self.make = self.get = lru_cache(maxsize, typed)(make)
        return self
    
    def __repr__(self) -> str: 
        make = self.make
        return f'{self.__class__.__name__}({make=!r})'




class _LegacyScopeVar(ScopeVar[T_Injected]):
    """Resolver t.Generic[T_InjectedObject"""

    __slots__ = 'value', 'get', 'make',

    value: T_Injected

    def __new__(cls, 
                value: T_Injected = Missing, 
                make: t.Union[Callable[..., T_Injected], None]=None, 
                *, 
                shared: t.Union[bool, None] = None):
        
        self = object.__new__(cls)

        if make is not None:
            self.make = make
            if shared is True:
                def get():
                    nonlocal make, value
                    if value is Missing:
                        value = make()
                    return value
                self.get = get
            else:
                self.get = make
        elif value is Missing:
            raise TypeError(f'{cls.__name__} one of value or call must be provided.')
        else:
            self.make = make
            self.get = lambda: value

        self.value = value
        return self

    def __repr__(self) -> str: 
        make, value = self.make, self.value,
        return f'{self.__class__.__name__}({value=!r}, make={getattr(make, "__func__", make)!r})'







T_Depends = t.TypeVar('T_Depends', covariant=True)




@export()
@Injectable.register
class Depends:

    """Annotates type as a `Dependency` that can be resolved by the di.
    
    Example: 
        Depends(typ, on=Injectable, at='scope_name') # type(injector[Injectable]) = typ

    """
    __slots__ = 'on', 'at', 'arguments', '_hash', '__weakref__',

    on: Injectable
    at: str
    arguments: Arguments

    def __new__(cls, 
                tp: T_Depends=..., 
                on: Injectable = ..., 
                /, 
                *args, 
                **kwargs):

        if on is ...:
            on = tp
            if not isinstance(tp, (type, GenericAlias, t.TypeVar)):
                tp = ...
                
        arguments = Arguments(args, kwargs)

        if isinstance(on, cls):
            ann = on.replace(arguments=on.arguments.extend(arguments))
        else:
            ann = object.__new__(cls)
            ann.on = on
            ann.arguments = arguments
        
        if tp is ...:
            return ann
        elif get_origin(tp) is t.Annotated:
            if ann == next((a for a in reversed(tp.__metadata__) if isinstance(a, cls)), None):
                return tp

        try:
            ret = t.Annotated[tp, ann]
        except TypeError as e:
            raise TypeError(
                f'{cls.__name__}(type, /, *, on: Injectable = ..., at: str =...) '
                f'should be used with at least one type argument.'
            ) from e
        else:
            return ret

    @property
    def __origin__(self):
        return self.__class__

    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__module__}.Depends")

    def __eq__(self, x) -> bool:
        if isinstance(x, Depends):
            return self.on == x.on and self.at == x.at \
                and self.arguments == x.arguments
        return NotImplemented

    def __hash__(self) -> bool:
        try:
            return self._hash
        except AttributeError:
            self._hash = hash((self.on, self.at, self.arguments))
            return self._hash

    def __repr__(self) -> bool:
        return f'{self.__class__.__name__}(on={self.on}, at={self.at}, arguments={self.arguments!r})'
    
    def replace(self,
                *, 
                on: Injectable = ..., 
                args: tuple=(), 
                kwargs: Mapping[str, t.Any]=frozendict(),
                arguments: Arguments=...) -> 'Depends':
        
        if arguments is ...:
            arguments = self.arguments.replace(args, kwargs)

        return self.__class__(
            on=self.on if on is ... else on,
            arguments=arguments
        )
    


