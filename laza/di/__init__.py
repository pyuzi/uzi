from abc import abstractmethod, ABCMeta
from logging import getLogger
import typing as t


from typing_extensions import Self
from laza.common import text
from laza.common.collections import frozendict
from laza.common.imports import ImportRef

from laza.common.functools import export, calling_frame, cache, Missing
from laza.common.data import DataPath




from types import FunctionType, GenericAlias, new_class







if t.TYPE_CHECKING:
    from .providers import Provider
    from .injectors import Injector
    from .containers import Container
    ProviderType = type[Provider]




T_Injected = t.TypeVar("T_Injected", covariant=True)
T_Default = t.TypeVar("T_Default")
T_Injectable = t.TypeVar('T_Injectable', bound='Injectable', covariant=True)

# export('T_Injected', 'T_Injectable', 'T_Default')

_logger = getLogger(__name__)


@export()
def isinjectable(obj):
    return isinstance(obj, Injectable)




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









class _InjectableMeta(ABCMeta):

    def register(self, subclass):
        if not (calling_frame().get('__package__') or '').startswith(__package__):
            raise TypeError(f'virtual subclasses not allowed for {self.__name__}')

        return super().register(subclass)



    

@export()
class Injectable(metaclass=_InjectableMeta):

    __slots__ = ()

    __class_getitem__ = classmethod(GenericAlias)

    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__name__}")


Injectable.register(type)
Injectable.register(t.TypeVar)
Injectable.register(FunctionType)
Injectable.register(GenericAlias)
Injectable.register(type(t.Generic[T_Injected]))
Injectable.register(type(t.Union))
Injectable.register(InjectedLookup)
Injectable.register(ImportRef)





    

@export()
@Injectable.register
class InjectionMarker(t.Generic[T_Injectable], metaclass=ABCMeta):

    __slots__ = '__injects__',  '__metadata__', '_hash',

    __injects__: T_Injectable
    __metadata__: frozendict

    @property 
    @abstractmethod
    def __dependency__(self) -> T_Injectable: 
        ...

    def __new__(cls: type[Self], inject: T_Injectable, metadata: dict=(), /):
        if not isinjectable(inject):
            raise TypeError(
                f'`dependency` must be an Injectable not '
                f'`{inject.__class__.__name__}`'
            )

        self = object.__new__(cls)
        self.__injects__ = inject
        self.__metadata__ = frozendict(metadata)
        return self
    
    _create = classmethod(__new__)
    
    @property
    def __origin__(self):
        return self.__class__

    def _clone(self, metadata: dict=(), /, **extra_metadata):
        metadata = frozendict(metadata or self.__metadata__, **extra_metadata)
        return self._create(self.__injects__, metadata)
    
    def __getitem__(self: Self, type_: type[T_Injected]):
        """Annotate given type with this marker.
        
        Calling `marker[T]` is the same as `Annotated[type_, marker]`
        """
        if type_.__class__ is tuple:
            type_ = t.Annotated[type_] # type: ignore
        
        return t.Annotated[type_, self] 

    def __reduce__(self):
        return self._create, (self.__injects__, self.__metadata__)
    
    def __eq__(self, x) -> bool:
        if not isinstance(x, self.__class__):
            return not self.__metadata__ and x == self.__injects__
        return self.__injects__ == x.__injects__\
            and self.__metadata__ == x.__metadata__
        
    def __hash__(self):
        try:
            return self._hash
        except AttributeError:
            if self.__metadata__:
                self._hash = hash((self.__injects__, self.__metadata__))
            else:
                self._hash = hash(self.__injects__)
            return self._hash
           
    def __setattr__(self, name: str, value) -> None:
        if hasattr(self, '_hash'):
            getattr(self, name)
            raise AttributeError(f'cannot set readonly attribute {name!r}')

        return super().__setattr__(name, value)    




_T_Dot = t.Literal['.', '..', '...', '....']


@export()
class Inject(InjectionMarker[T_Injectable]):

    """Marks an injectable as a `dependency` to be injected.
    """
    __slots__ = ()

    def __new__(cls, 
                inject: T_Injectable, *,
                scope: t.Union['Injector', _T_Dot]=Missing,
                default=Missing):
        metadata = {}
        scope is Missing or metadata.update(scope=scope)
        default is Missing or metadata.update(default=default)
        return super().__new__(cls, inject, metadata)

    @property
    def __dependency__(self):
        return self if self.__metadata__ else self.__injects__

    @property
    def __default__(self):
        return self.__metadata__.get('default')

    @property
    def __scope__(self):
        return self.__metadata__.get('scope')

    @property
    def is_optional(self):
        return 'default' in self.__metadata__

    def optional(self, default=None):
        return self._clone(default=default)

    def scope(self, scope=None):
        return self._clone(scope=scope)

    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__module__}.{cls.__name__}")

    def __repr__(self) -> bool:
        dependency = self.__injects__
        scope = self.__scope__ # or ... #'...'
        default = self.__default__ # '...' if self.__default__ is Parameter.empty else self.__default__
        return f'{self.__class__.__name__}({dependency=}, {default=}, {scope=})'


