from abc import abstractmethod, ABCMeta
from functools import cache
from logging import getLogger
import sys
import typing as t

from collections.abc import Mapping, Iterable, Hashable
from laza.common import text
from laza.common.collections import Arguments, frozendict
from laza.common.imports import ImportRef
from laza.common.proxy import unproxy

from laza.common.functools import export, Void, calling_frame
from laza.common.data import DataPath

from laza.common.enum import IntEnum, auto


from collections.abc import Callable

from types import FunctionType, GenericAlias, MethodType, new_class


from .exc import InjectorKeyError
from .typing import get_all_type_hints, get_args, get_origin, InjectableForm, get_type_parameters


logger = getLogger(__name__)





if t.TYPE_CHECKING:
    from . import Provider, Injector, IocContainer
    ProviderType = type[Provider]




T_Injected = t.TypeVar("T_Injected")
T_Default = t.TypeVar("T_Default")
T_Injectable = t.TypeVar('T_Injectable', bound='Injectable', covariant=True)

export('T_Injected', 'T_Injectable', 'T_Default')



@export()
class InjectionToken(t.Generic[T_Injected]):

    __slots__ = '__name__', '__weakref__'

    __name__: str
    __type__: type[T_Injected]

    __new_type = False 

    @classmethod
    @cache
    def __class_getitem__(cls, params):
        aka: GenericAlias = super().__class_getitem__(params)
        ns = dict(__type__=aka.__args__[0])
        name = f'{text.uppercamel(aka.__origin__.__name__)}{cls.__name__}'
        cls.__new_type = True
        res = new_class(name, (aka,), None, lambda dct: dct.update(ns))
        cls.__new_type = False
        return res

    def __init_subclass__(cls, *args, **kwargs):
        if cls.__new_type is not True:
            raise TypeError(f"Cannot subclass {cls.__name__}")

    def __new__(cls, name: str):
        if name.__class__ is not str:
            raise TypeError(f'name must be str not {name.__class__.__name__}')

        self = object.__new__(cls)
        self.__name__ = name
        return self

    def __copy__(self):
        return self

    def __deepcopy__(self, memo=None):
        return self

    def __reduce__(self):
        return self.__name__

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.__name__!r})'






@export()
class InjectedLookup(t.Generic[T_Injected]):

    __slots__ = '__args__', '__weakref__'

    __name__: str
    __type__: type[T_Injected]

    __new_type = False 

    @classmethod
    @cache
    def __class_getitem__(cls, params):
        aka: GenericAlias = super().__class_getitem__(params)
        ns = dict(__type__=aka.__args__[0])
        name = f'{text.uppercamel(aka.__origin__.__name__)}{cls.__name__}'
        cls.__new_type = True
        res = new_class(name, (aka,), None, lambda dct: dct.update(ns))
        cls.__new_type = False
        return res

    def __init_subclass__(cls, *args, **kwargs):
        if cls.__new_type is not True:
            raise TypeError(f"Cannot subclass {cls.__name__}")

    @classmethod
    @cache
    def __class_getitem__(cls, params):
        aka: GenericAlias = super().__class_getitem__(params)
        ns = dict(__type__=aka.__args__[0])
        name = f'{text.uppercamel(aka.__origin__.__name__)}InjectionToken'
        return new_class(name, (aka,), None, lambda dct: dct.update(ns))

    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__name__}")

    def __init__(self, depends: 'Injectable', lookup):
        self.__args__ = depends,  DataPath(lookup)

    @property
    def __origin__(self):
        return InjectedLookup

    @property
    def depends(self):
        return self.__args__[0]

    @property
    def path(self):
        return self.__args__[1]

    def __hash__(self):
        return hash(self.__args__)

    def __eq__(self, x):
        if isinstance(x, InjectedLookup):
            return self.__args__ == x.__args__
        return NotImplemented

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.depends}, path={self.path!r})'







@export()
# @InjectableForm.register
class InjectableAlias(GenericAlias):

    __slots__ = ()

    @property
    def __injectable_origin__(self):
        return Injectable

    # def __eq__(self, x):
    #     if isinstance(x, InjectableAlias):
    #         return self.__origin__ == x.__origin__
    #     else:
    #         return self.__origin__.__eq__(x)

    # def __hash__(self):
    #     return hash(self.__origin__)




@export()
class InjectableType(ABCMeta):


    def register(self, subclass):
        if not (calling_frame().get('__package__') or '').startswith(__package__):
            raise TypeError(f'virtual subclasses not allowed for {self.__name__}')

        return super().register(subclass)



    

@export()
class Injectable(metaclass=InjectableType):

    __slots__ = ()

    __class_getitem__ = classmethod(GenericAlias)

    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass Injectable")

    @t.overload
    def __new__(cls, *params: 'Injectable') -> InjectableAlias:
        ...
        
    @t.overload
    def __new__(cls, name: str) -> InjectionToken:
        ...
        
    def __new__(cls, *params):
        plen = len(params)
        
        if plen == 0:
            raise ValueError(f'atleast 1 type parameter is required 0 given.')
        elif plen == 1:
            param = params[0]
            ptyp = param.__class__
            if ptyp is str:
                return InjectionToken(param)
            elif issubclass(ptyp, cls):
                return param
            else:
                raise TypeError(f'Expected Injectable or str not {ptyp.__name__!r}')
        elif all(isinstance(p, cls) for p in params):
            return InjectableAlias(cls, params)
        else:
            typs = ', '.join(f'{p.__class__.__name__!r}' for p in params if not isinstance(p, cls))
            raise TypeError(f'parameters must be Injectable types not ({typs})')

    @classmethod
    @cache
    def __class_getitem__(cls, params: tuple):
        if not isinstance(params, tuple):
            params = params,
        
        if len(params) > 1:
            params = t.Union[params], # type: ignore
        elif not params:
            raise ValueError(f'atleast 1 type parameter is required 0 given.')

        return InjectableAlias(params[0], params)



Injectable.register(type)
Injectable.register(t.TypeVar)
Injectable.register(MethodType)
Injectable.register(FunctionType)
Injectable.register(GenericAlias)
Injectable.register(type(t.Generic[T_Injected]))
Injectable.register(type(t.Union))
Injectable.register(InjectionToken)
Injectable.register(InjectedLookup)
Injectable.register(ImportRef)





@export()
class ResolverFunc(Callable[['Injector'], T_Injected], t.Generic[T_Injected]):

    @abstractmethod
    def __call__(self, injector: 'Injector') -> t.Union['InjectorVar[T_Injected]', None]:
        ...

    @classmethod
    def __subclasshook__(cls, sub):
        if cls is ResolverFunc:
            try:
                return issubclass(sub, (FunctionType, MethodType, type)) or callable(getattr(sub, '__call__'))
            except AttributeError:
                pass
            
        return NotImplemented
    
    __class_getitem__ = classmethod(GenericAlias)




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
    # variant: 'KindOfProvider'     = auto()
    
    meta: 'KindOfProvider'        = auto()
    
    factory: 'KindOfProvider'     = auto()
    resolver: 'KindOfProvider'    = auto()

    if t.TYPE_CHECKING:
        default_impl: 'ProviderType'

    def _set_default_impl(self, cls: 'ProviderType'):
        # if self.default_impl not in {cls, None}:
        #     raise ValueError(f'{cls}. {self}.impl already set to {self.default_impl}')
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
            self.make = make
            self.get = lambda: value


        self.injector = injector
        self.value = value
        return self

    def __repr__(self) -> str: 
        make, value = self.make, self.value,
        return f'{self.__class__.__name__}({self.injector}, {value=!r}, make={getattr(make, "__func__", make)!r})'





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
                /, *, 
                on: Injectable = ..., 
                at: str =..., 
                args: tuple=(), 
                kwargs: Mapping[str, t.Any]=frozendict(),
                arguments: Arguments=...):

        if arguments is ...:
            arguments = Arguments(args, kwargs)
        else:
            arguments = Arguments.coerce(arguments)

        if isinstance(on, cls):
            ann = on.replace(at=at, arguments=on.arguments.extend(arguments))
        else:
            ann = object.__new__(cls)
            # if on is ...:
            #     if tp is ...:
            #         raise TypeError(
            #             f'{cls.__name__}(type, /, *, on: Injectable = ..., at: str =...) '
            #             f'should be used with at least the `type` or the dependency argument `on`.'
            #         )
            ann.on = on
            ann.at = at 
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
                at: str =..., 
                args: tuple=(), 
                kwargs: Mapping[str, t.Any]=frozendict(),
                arguments: Arguments=...) -> 'Depends':
        
        if arguments is ...:
            arguments = self.arguments.replace(args, kwargs)

        return self.__class__(
            on=self.on if on is ... else on,
            at=self.at if at is ... else at,
            arguments=arguments
        )
    






@export()
class InjectedProperty(t.Generic[T_Injected]):
    
    __slots__ = 'depends', 'ioc', '__name__', 'default', '__weakref__'

    _ioc: 'IocContainer'
    default: T_Default
    depends: Depends
    __name__: str

    def __init__(self, 
                dep: Injectable = ..., 
                default: T_Default=..., *,
                scope: str=..., 
                args: tuple=(),
                kwargs: Mapping=frozendict(),
                arguments: Arguments=...,
                ioc: t.Union['IocContainer', None]=None) -> T_Injected:

        self.default = default
        self.ioc = unproxy(ioc)

        self.depends = Depends(on=dep, at=scope, args=args, kwargs=kwargs, arguments=arguments)

    @property
    def dep(self):
        return self.depends.on

    @property
    def scope(self):
        return self.depends.at

    def __set_name__(self, owner, name):
        self.__name__ = name

        if self.dep is ...:
            if mod := getattr(owner, '__module__', None):
                mod = sys.modules[mod].__dict__
            hints = get_all_type_hints(owner, globalns=mod) 
            dep = hints and hints.get(name) or None

            if dep is None:
                raise TypeError(
                    f'Injectable not set for {owner.__class__.__name__}.{name}'
                )
            
            self.depends = self.depends.replace(on=dep)

    def __get__(self, obj, typ=None) -> T_Injected:
        if obj is None:
            return self

        from .container import ioc

        try:
            return (self.ioc or ioc)[self.depends]
        except InjectorKeyError as e:
            if self.default is ...:
                raise AttributeError(self) from e
            return self.default

    def __str__(self) -> T_Injected:
        return f'{self.__class__.__name__}({self.depends!r})'

    def __repr__(self) -> T_Injected:
        return f'<{self.__name__} = {self}>'






@export()
class InjectedClassVar(InjectedProperty[T_Injected]):

    __slots__ = ()

    def __get__(self, obj, typ=...) -> T_Injected:
        return super().__get__(typ, typ)


if t.TYPE_CHECKING:
    InjectedClassVar = t.Final[T_Injected]


