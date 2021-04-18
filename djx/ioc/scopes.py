from collections import defaultdict
from collections.abc import Mapping, MutableMapping, Collection
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, ClassVar, Generic, NamedTuple, Optional, Sequence, Type, TypeVar, Union


from flex.utils import text
from flex.utils.decorators import export, lookup_property
from flex.utils.metadata import metafield, BaseMetadata, get_metadata_class


from .exc import ProviderNotFoundError
from .providers import ProviderStack, Provider
from .symbols import symbol, _ordered_id
from .injectors import Injector, NullInjector
from .reg import registry
from . import abc



_T_Conf = TypeVar('_T_Conf', bound='ScopeConfig')
_T_Scope = abc._T_Scope


_T_Injected = abc._T_Injected
_T_Injector = abc._T_Injector
_T_Provider = abc._T_Provider

_T_Injectable = abc._T_Injectable

_T_Cache = abc._T_Cache
_T_Providers =  abc._T_Providers


_scope_types: abc.PriorityStack[str, 'ScopeType[_T_Scope]'] = abc.PriorityStack()


_sym_any = symbol(abc.ANY_SCOPE)
_sym_main = symbol(abc.MAIN_SCOPE)


__scope_key_var = ContextVar('__scope_key_var')
__state_ctx_var = ContextVar['ScopeContext']('__state_ctx_var')

@export()
@contextmanager
def scope(name: str=abc.Scope.MAIN):
    cur, injs = __state_ctx_var.get(_null_scope_ctx)

    token = None
    if name not in injs:
        injs = injs.copy()
        injs[name] = registry.scopes[name].create_injector(injs[cur])
        token = __state_ctx_var.set(ScopeContext(cur := name, injs))

    try:
        with injs[cur] as inj:
            yield inj
    finally:
        if token is not None:
            __state_ctx_var.reset(token)
    


@export()
def current_injector():
    cur, injs = __state_ctx_var.get(_null_scope_ctx)
    return injs[cur]



class ScopeContext(NamedTuple):
    current: str
    injectors: dict[str, _T_Injector]
    


_null_scope_ctx = ScopeContext(None, { None: NullInjector() })


@export()
class ScopeConfig(BaseMetadata[_T_Scope]):

    is_abstract = metafield[bool]('abstract', default=False, inherit=False)

    @metafield[int](inherit=False)
    def _pos(self, value) -> int:
        return _ordered_id()
    
    @metafield[str](inherit=True)
    def name(self, value, base=None) -> str:
        return value or base or text.snake(self.target.__name__)
    
    @metafield[int](inherit=True, default=1)
    def priority(self, value, base=None) -> int:
        return base or 0 if value is None else value
    
    @metafield[type[_T_Injector]](inherit=True)
    def injector_class(self, value, base=None) -> type[_T_Injector]:
        return value or base or Injector
    
    @metafield[type[_T_Cache]](inherit=True)
    def cache_class(self, value, base=None) -> type[_T_Cache]:
        return value or base or dict
    
    @metafield[list[str]](inherit=False)
    def aliases(self, value: Collection[str]) -> list[str]:
        _seen = set()
        seen = lambda p: p in _seen or _seen.add(p)
        return [p for p in value or () if not seen(p)]



@export
@abc.ScopeConfig.register
class ScopeType(abc.ABCMeta):
    
    conf: _T_Conf

    def __new__(mcls, name, bases=None, dct=None) -> 'ScopeType[_T_Scope]':

        if bases is None and dct is None:
            return _scope_types[name]
        
        raw_conf = dct.get('Config')
                
        meta_use_cls = raw_conf and getattr(raw_conf, '__use_class__', None)
        meta_use_cls and dct.update(__config_class__=meta_use_cls)

        cls: ScopeType[_T_Scope, _T_Conf] = super().__new__(mcls, name, bases, dct)

        conf_cls = get_metadata_class(cls, '__config_class__')
        conf_cls(cls, 'conf', raw_conf)

        if not cls.conf.is_abstract:
            registry.add_scope(cls)

        return cls

    #
    def __cls_order__(cls):
        return (cls.conf.priority, symbol(cls.conf.name), cls.conf._pos)
        
    def __ge__(cls, x) -> bool:
        return cls.__cls_order__() >= x

    def __gt__(cld, x) -> bool:
        return cld.__cls_order__() > x

    def __le__(cls, x) -> bool:
        return cls.__cls_order__() <= x

    def __lt__(cls, x) -> bool:
        return cls.__cls_order__() < x




@export
class Scope(abc.Scope[_T_Injector, _T_Conf], Generic[_T_Injector, _T_Conf], metaclass=ScopeType):
    """"""

    conf: ClassVar[_T_Conf]
    __pos: int
    class Config:
        __use_class__ = ScopeConfig
        abstract = True

    name: str = lookup_property('name', 'conf')
    priority: int = lookup_property('priority', 'conf')
    injector_class: type[_T_Injector] = lookup_property('injector_class', 'conf')
    cache_class: type[_T_Cache] = lookup_property('cache_class', 'conf')
 
    def __init__(self) -> None:
        self.__pos = _ordered_id()
        self.collect_providers()

    def collect_providers(self):
        self.providers = registry.collect_providers(self.name, *self.conf.aliases)

    def setup(self, inj: _T_Injector) -> _T_Injector:
        self.setup_providers(inj)
        self.setup_cache(inj)
        return inj

    def teardown(self, inj: _T_Injector):
        inj.cache = None
        inj.providers = None

    def setup_providers(self, inj: _T_Injector):
        inj.providers = self.providers

    def setup_cache(self, inj: _T_Injector):
        inj.cache = self.cache_class()

    def create_injector(self, parent: _T_Injector) -> _T_Injector:
        return self.injector_class(self, parent)
#
    def __order__(self):
        return self.__pos, self.__class__
        
    def __ge__(self, x) -> bool:
        return self.__order__() >= x

    def __gt__(self, x) -> bool:
        return self.__order__() > x

    def __le__(self, x) -> bool:
        return self.__order__() <= x

    def __lt__(self, x) -> bool:
        return self.__order__() < x

    def __eq__(self, x) -> bool:
        return self.__order__() == x

    def __hash__(self) -> int:
        return hash(self.__order__())
    




class MainScope(Scope):

    class Config:
        name = Scope.MAIN






