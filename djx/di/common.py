import typing as t

from collections.abc import Mapping, Iterable

from djx.common.utils import export, Void

from djx.common.enum import IntEnum, auto


from collections.abc import Callable

from types import MethodType






if t.TYPE_CHECKING:
    from .injectors import Injector


from .abc import T_Injectable, T_Injected, ResolverFunc

if t.TYPE_CHECKING:
    from . import Provider
    ProviderType = type[Provider]





@export()
class ResolverInfo(t.NamedTuple):

    func: t.Union[ResolverFunc, None] = None
    depends: set[T_Injectable] = frozenset()

    @classmethod
    def coerce(cls, obj):
        if obj is None:
            return cls()
        typ = obj.__class__
        if typ is cls:
            return obj
        elif issubclass(typ, tuple):
            return cls(*obj)
        elif issubclass(typ, Mapping):
            return cls(**obj)
        elif issubclass(typ, ResolverFunc):
            return cls(obj)
        elif issubclass(typ, Iterable):
            return cls(*obj)
        else:
            raise TypeError(f'must be ResolverFunc, Iterable, Mapping or None not {typ.__name__}')
    
    def __bool__(self):
        return self.func is not None



@export()
class KindOfProvider(IntEnum, fields='default_impl', frozen=False):
    value: 'KindOfProvider'       = auto()

    func: 'KindOfProvider'        = auto()
    type: 'KindOfProvider'        = auto()
    

    alias: 'KindOfProvider'       = auto()
    variant: 'KindOfProvider'     = auto()
    
    meta: 'KindOfProvider'        = auto()
    
    factory: 'KindOfProvider'     = auto()
    resolver: 'KindOfProvider'    = auto()

    if t.TYPE_CHECKING:
        default_impl: 'ProviderType'

    def _set_default_impl(self, cls: 'ProviderType'):
        if self.default_impl is not None:
            raise ValueError(f'{cls}. {self}.impl already set to {self.default_impl}')
        self.__member_data__[self.name].default_impl = cls
        cls.kind = self
        return cls

    @classmethod
    def _missing_(cls, val):
        if val is None:
            return cls.factory
    



@export()
class InjectorVar(t.Generic[T_Injected]):
    """Resolver t.Generic[T_InjectedObject"""

    __slots__ = 'injector', 'value', 'get', 'make',

    injector: 'Injector'
    value: T_Injected
    call: Callable[..., T_Injected]
    make: Callable[[], T_Injected]

    _default_cache_: t.ClassVar[t.Union[bool, None]] = None
    _default_bind_: t.ClassVar[t.Union[bool, None]] = None

    def __new__(cls, 
                injector: 'Injector', 
                /,
                value: T_Injected = Void, 
                make: t.Union[Callable[..., T_Injected], None]=None, 
                *, 
                bind: t.Union[bool, None] = None,
                cache: t.Union[bool, None] = None):
        
        self = object.__new__(cls)

        if make is not None:
            if bind is True or (bind is None and cls._default_bind_):
                self.make = make = MethodType(make, self)
            else:
                self.make = make

            if cache is True or (cache is None and cls._default_cache_):
                def get():
                    nonlocal self
                    if self.value is Void:
                        self.value = self.make()
                    return self.value
                self.get = get
            else:
                self.get = make
        elif value is Void:
            raise TypeError(f'{cls.__name__} one of value or call must be provided.')
        else:
            self.get = self.make = make

        self.injector = injector
        self.value = value
        return self

    def __repr__(self) -> str: 
        make, value = self.make, self.value,
        return f'{self.__class__.__name__}({self.injector}, {value=!r}, make={getattr(make, "__func__", make)!r})'
