import logging
from collections import defaultdict
from collections.abc import Mapping, MutableMapping, Collection
from contextlib import contextmanager
from contextvars import ContextVar
from functools import partial
from itertools import chain
from typing import Any, Callable, ClassVar, Generic, NamedTuple, Optional, Sequence, Type, TypeVar, Union


from flex.utils import text
from flex.utils.proxy import Proxy
from flex.utils.decorators import cached_property, export, lookup_property
from flex.utils.metadata import metafield, BaseMetadata, get_metadata_class


from .exc import ProviderNotFoundError
from .providers import ProviderStack, Provider, provide
from .symbols import symbol, _ordered_id
from .injectors import Injector, NullInjector
from .reg import registry
from . import abc

__all__ = [
    'injector',
]


logger = logging.getLogger(__name__)


_T_Conf = TypeVar('_T_Conf', bound='Config')
_T_Scope = abc._T_Scope


_T_Injected = abc._T_Injected
_T_Injector = abc._T_Injector
_T_Provider = abc._T_Provider

_T_Injectable = abc._T_Injectable

_T_Cache = abc._T_Cache
_T_Providers =  abc._T_Providers



__inj_ctxvar = ContextVar[_T_Injector]('__inj_ctxvar')
__state_ctx_var = ContextVar['ScopeContext']('__state_ctx_var')

__null_inj = NullInjector()

@export()
@contextmanager
def scope(name: str=None):
    cur = __inj_ctxvar.get(__null_inj)

    reset = None
    scope = Scope(name) if name else Scope(Scope.MAIN) \
        if cur is __null_inj else cur.scope

    if scope not in cur:
        cur = scope.create(cur)
        reset = __inj_ctxvar.set(cur)
    try:
        with cur as inj:
            yield inj
    finally:
        reset and __inj_ctxvar.reset(reset)
  



@export()
def current():
    return __inj_ctxvar.get(__null_inj)



@export()
def head():
    return __inj_ctxvar.get(__null_inj).head


@export()
def get(key: _T_Injectable, default=None) -> _T_Injected:
    return head().get(key, default)



injector = Proxy(head)






@export()
@abc.ScopeConfig.register
class Config(BaseMetadata[_T_Scope]):

    is_abstract = metafield[bool]('abstract', default=False)

    @metafield[int]()
    def _pos(self, value) -> int:
        return _ordered_id()
    
    @metafield[str](inherit=True)
    def name(self, value: str, base: str=None) -> str:
        if not self.is_abstract:
            rv = value or base or self.target.__name__
            assert rv.isidentifier(), f'Scope name must be avalid identifier.'
            return self.target._make_name(rv)
        
    @metafield[int](inherit=True)
    def priority(self, value, base=1) -> int:
        return base or 0 if value is None else value
    
    @metafield[bool](inherit=True, default=None)
    def embed_only(self, value, base=False):
        return value if value is not None else base
    
    @metafield[bool](inherit=True, default=None)
    def implicit(self, value, base=False):
        return value if value is not None else base
    
    @metafield[type[_T_Injector]](inherit=True)
    def injector_class(self, value, base=None) -> type[_T_Injector]:
        return value or base or Injector
    
    @metafield[type[_T_Cache]](inherit=True)
    def cache_class(self, value, base=None) -> type[_T_Cache]:
        return value or base or dict
    
    @metafield[list[str]](inherit=True)
    def depends(self, value: Collection[str], base=()) -> list[str]:
        _seen = set((self.name,))
        self.embed_only and _seen.update((abc.Scope.MAIN, abc.Scope.ANY))
        seen = lambda p: p in _seen or _seen.add(p)
        value = value if value is not None else base or ()
        value = value if self.embed_only else chain((abc.Scope.ANY, abc.Scope.MAIN), value)
        return [p for p in value if not seen(p)]





@export
@abc.ScopeConfig.register
class ScopeType(abc.ABCMeta):
    
    conf: _T_Conf

    def __new__(mcls, name, bases=None, dct=None) -> 'ScopeType[_T_Scope]':

        if bases is dct is None:
            name = mcls._make_name(name)
            if name in registry.scope_types:
                return registry.scope_types[name]
            else:
                return mcls(name, (ImplicitScope,), {})


        raw_conf = dct.get('Config')
                
        meta_use_cls = raw_conf and getattr(raw_conf, '__use_class__', None)
        meta_use_cls and dct.update(__config_class__=meta_use_cls)

        cls: ScopeType[_T_Scope, _T_Conf] = super().__new__(mcls, name, bases, dct)

        conf_cls = get_metadata_class(cls, '__config_class__', base=Config, name='Config')
        conf_cls(cls, 'conf', raw_conf)

        if not cls.conf.is_abstract:
            cls._Scope__instance = None
            registry.add_scope(cls)

        return cls
    
    @classmethod
    def _make_name(cls, name):
        return name.conf.name if isinstance(name, ScopeType) else text.snake(name)

#
    def __cls_order__(cls):
        return (cls.conf.priority, cls.conf._pos, cls)
        
    def __ge__(cls, x) -> bool:
        return cls.__cls_order__() >= x

    def __gt__(cld, x) -> bool:
        return cld.__cls_order__() > x

    def __le__(cls, x) -> bool:
        return cls.__cls_order__() <= x

    def __lt__(cls, x) -> bool:
        return cls.__cls_order__() < x

    def __repr__(cls) -> str:
        return f'<ScopeType({cls.__name__}, {cls.conf!r}>'
    
    def __str__(cls) -> str:
        return f'<ScopeType({cls.__name__}, {cls.conf.name!r}>'




_config_lookup = partial(lookup_property, lookup='conf', read_only=True)

@export
class Scope(abc.Scope[_T_Injector, _T_Conf], Generic[_T_Injector, _T_Conf, _T_Provider], metaclass=ScopeType):
    """"""

    conf: ClassVar[_T_Conf]
    __pos: int
    class Config:
        abstract = True

    name: str = _config_lookup()
    embed_only: bool = _config_lookup()
    priority: int = _config_lookup()
    injector_class: type[_T_Injector] = _config_lookup()
    cache_class: type[_T_Cache] = _config_lookup()
    
    def __new__(cls, name=None, /):
        cls = ScopeType(name or cls)
        if cls.conf.is_abstract:
            raise TypeError(f'Cannot create scope {cls}. {cls.conf.is_abstract=}')
        elif cls._Scope__instance is None:
            cls._Scope__instance = super().__new__(cls)
        
        return cls._Scope__instance

    def __init__(self, *args) -> None:
        self.__pos = 0
        assert self.__class__._Scope__instance is self, (
            f'Scope are singletons. {self} already created.'
        )

    @property
    def is_ready(self):
        return self.__pos > 0

    @property
    def embeds(self):
        return list(s for s in self.depends if s.embed_only)

    @property
    def depends(self):
        for n in self.conf.depends:
            yield Scope(n)
          
    @property
    def parents(self):
        return list(s for s in self.depends if not s.embed_only)

    @property
    def providers(self):
        try:
            return self.__dict__['providers']
        except KeyError:
            self.__dict__['providers'] = {
                    p.abstract(): p for p in self.providerstack.values() 
                }
            self.prepare()
            return self.__dict__['providers']

    @property
    def providerstack(self):
        try:
            return self.__dict__['providerstack']
        except KeyError:
            self.__dict__['providerstack'] = self._make_providerstack()
            self.prepare()
            return self.__dict__['providerstack']

    def prepare(self: _T_Scope, *, strict=False) -> _T_Scope:
        if hasattr(self, '__pos'):
            if strict:
                raise RuntimeError(f'Scope {self} already prepared')
        else:
            self._prepare()
            self.__pos = _ordered_id()

        return self

    def _prepare(self):
        logger.debug(f'prepare({self})')

    def _make_providerstack(self):
        stack = abc.PriorityStack()

        for embed in sorted(self.embeds):
            stack.update(embed.providers)
            provide(embed.__class__, value=embed, scope=self.name)
        
        provide(Scope, self.__class__, value=self, scope=self.name)
        stack.update(registry.all_providers[self.name])
        return stack
    
    def setup(self, inj: _T_Injector) -> _T_Injector:
        logger.debug(f'setup({self}):  {inj}')

        self.prepare()
        self.setup_providers(inj)
        self.setup_cache(inj)
        return inj

    def teardown(self, inj: _T_Injector):
        logger.debug(f'teardown({self}):  {inj}')

        inj.cache = None
        inj.providers = None

    def setup_providers(self, inj: _T_Injector):
        inj.providers = self.providers

    def setup_cache(self, inj: _T_Injector):
        inj.cache = self.cache_class()

    def create(self, parent: _T_Injector) -> _T_Injector:
        if self in parent:
            return parent
        
        logger.debug(f'create({self}):  parent = {parent}')
        
        for scope in sorted(self.parents):
            if scope not in parent:
                parent = scope.create(parent)
            
        return self.injector_class(self, parent)
#
    def __contains__(self, x) -> None:
        if isinstance(x, Scope):
            return x is self or any(True for s in self.depends if x in s)
        return False

    def __reduce__(self) -> None:
        return self.__class__, self.name

    def __order__(self):
        return self.__class__
        
    def __ge__(self, x) -> bool:
        return self.__order__() >= x

    def __gt__(self, x) -> bool:
        return self.__order__() > x

    def __le__(self, x) -> bool:
        return self.__order__() <= x

    def __lt__(self, x) -> bool:
        return self.__order__() < x

    def __eq__(self, x) -> bool:
        if isinstance(x, ScopeType):
            return x == self.__class__
        elif isinstance(x, Scope):
            return x.__class__ == self.__class__
        else:
            return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__class__)
#
    def __str__(self) -> str:
        return f'{self.__class__.__name__}({self.conf.name!r} #{self.ready and self.__pos or ""})'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.conf.name!r}, #{self.ready and self.__pos or ""}, {self.conf!r})'





class EmbeddedScope(Scope):

    class Config:
        abstract = True
        embed_only = True




class ImplicitScope(EmbeddedScope):
    class Config:
        abstract = True
        implicit = True





class AnyScope(EmbeddedScope):
    class Config:
        name = Scope.ANY






class MainScope(Scope):

    class Config:
        name = Scope.MAIN













