from abc import abstractmethod, ABCMeta
from inspect import Parameter
from logging import getLogger
from threading import Lock
import sys
import typing as t


from threading import Lock
from collections import Counter

from collections.abc import Mapping
from laza.common import text
from laza.common.collections import Arguments, frozendict
from laza.common.imports import ImportRef
from laza.common.proxy import unproxy

from laza.common.functools import export, calling_frame, cache, Missing
from laza.common.data import DataPath



from collections.abc import Callable

from types import FunctionType, GenericAlias, MethodType, new_class

from pyparsing import empty



from .exc import InjectorKeyError
from .typing import get_all_type_hints, get_origin



if t.TYPE_CHECKING:
    from . import Provider, Injector, IocContainer
    ProviderType = type[Provider]




T_Injected = t.TypeVar("T_Injected", covariant=True)
T_Default = t.TypeVar("T_Default")
T_Injectable = t.TypeVar('T_Injectable', bound='Injectable', covariant=True)

export('T_Injected', 'T_Injectable', 'T_Default')

logger = getLogger(__name__)



@export()
def isinjectable(obj):
    return isinstance(obj, Injectable)






__uid_map = Counter()
__uid_lock = Lock()

@export()
def unique_id(ns=None):
    global __uid_map, __uid_lock
    with __uid_lock:
        __uid_map[ns] += 1
        return __uid_map[ns]



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
    def __call__(self, injector: 'Injector') -> t.Union['ScopeVar[T_Injected]', None]:
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
                on: Injectable = ..., 
                tp: T_Depends=..., 
                /, 
                *args, 
                **kwargs):

        # if on is ...:
        #     on = tp
        #     if not isinstance(tp, (type, GenericAlias, t.TypeVar)):
        #         tp = ...
                
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
            return self.on == x.on 
            # and self.at == x.at \
            #     and self.arguments == x.arguments
        
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
    





@export()
@Injectable.register
class Dep(t.Generic[T_Injectable]):

    """A `Dependency` dependency marker.
    """
    __slots__ = '__dependency__', '__scope__', '__default__', '_hash', '__weakref__',

    __dependency__: T_Injectable
    __scope__: t.Union['IocContainer', 'Injector']
    __default__: t.Any

    def __new__(cls, 
                dependency: Injectable, *,
                default=Parameter.empty,
                scope: t.Union['IocContainer', 'Injector']=None):
        self = object.__new__(cls)
        self.__dependency__ = dependency
        self.__default__ = default
        self.__scope__ = scope
        return self
        
    @property
    def __origin__(self):
        return self.__class__

    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__module__}.{cls.__name__}")

    def __eq__(self, x) -> bool:
        if isinstance(x, self.__class__):
            return self.__dependency__ == x.__dependency__ \
                and self.__scope__ == x.__scope__\
                and self.__default__ == x.__default__
        elif self.__scope__ is None and self.__default__ is Parameter.empty:
            return self.__dependency__ == x

    def __hash__(self):
        try:
            return self._hash
        except AttributeError:
            if self.__scope__ is None and self.__default__ is Parameter.empty:
                self._hash = hash(self.__dependency__)
            else:
                self._hash = hash((self.__dependency__, self.__scope__, self.__default__))
            return self._hash
     
    def __repr__(self) -> bool:
        dependency = self.__dependency__
        scope = self.__scope__ or '...'
        default = '...' if self.__default__ is Parameter.empty else self.__default__
        return f'{self.__class__.__name__}({dependency=}, {default=}, {scope=})'
    



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

        from .containers import ioc

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


