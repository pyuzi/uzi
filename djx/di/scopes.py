from contextvars import ContextVar
import logging
from threading import RLock
from weakref import ref
from functools import partial
from itertools import chain
from typing import Callable, ClassVar, Generic
from collections import ChainMap
from collections.abc import Collection

from djx.common.collections import KeyedSet, fallbackdict
from djx.common.imports import ImportRef


from djx.common.utils import export, lookup_property, cached_property
from djx.common.metadata import metafield, BaseMetadata, get_metadata_class



from .providers import AliasProvider, InjectorProvider
from .inspect import ordered_id
from .injectors import Injector, InjectorContext, NullInjector, INJECTOR_TOKEN
from .abc import (
    ANY_SCOPE, COMMAND_SCOPE, LOCAL_SCOPE, MAIN_SCOPE, REQUEST_SCOPE,
    Injectable, ScopeConfig, 
    T_ContextStack, T_Injector, T_Provider, _T_Conf, T_Scope,
)

from . import abc, signals

logger = logging.getLogger(__name__)



_config_lookup = partial(lookup_property, source='config', read_only=True)



_INTERNAL_SCOPE_NAMES = fallbackdict(main=None, any=None)

@export()
class Config(BaseMetadata[T_Scope], ScopeConfig, Generic[T_Scope, T_Injector, T_ContextStack]):

    is_abstract = metafield[bool]('abstract', default=False)

    @metafield[int]()
    def _pos(self, value) -> int:
        return ordered_id()
    
    @metafield[str](inherit=True)
    def name(self, value: str, base: str=None) -> str:
        if not self.is_abstract:
            rv = value or base or self.target.__name__
            assert rv.isidentifier(), f'Scope name must be a valid identifier.'
            return self.target._get_scope_name(rv)
        
    @metafield[int](inherit=True)
    def priority(self, value, base=1) -> int:
        return base or 0 if value is None else value or 0
    
    @metafield[bool](inherit=True, default=None)
    def embedded(self, value, base=False):
        return value if value is not None else base
    
    @metafield[bool](inherit=True, default=None)
    def implicit(self, value, base=False):
        return value if value is not None else base or False
    
    @metafield[type[T_ContextStack]](inherit=True)
    def context_class(self, value, base=None):
        return value or base or InjectorContext
    
    @metafield[type[T_Injector]](inherit=True)
    def injector_class(self, value, base=None):
        return value or base or Injector
    
    @metafield[list[str]](inherit=True)
    def depends(self, value: Collection[str], base=()) -> list[str]:
        _seen = set((self.name,))
        tail = (abc.Scope.ANY,)
        self.embedded and _seen.update(tail)

        seen = lambda p: p in _seen or _seen.add(p)
        value = value if value is not None else base or ()
        value = value if self.embedded else chain((v for v in value if v not in tail), tail)
        return [p for p in value if not seen(p)]

    def __order__(self):
        return self.priority, self._pos
        



@export
@abc.ScopeConfig.register
class ScopeType(abc.ScopeType):
    
    config: _T_Conf
    __instance__: T_Scope

    def __new__(mcls, name, bases, dct) -> 'ScopeType[T_Scope]':
        raw_conf = dct.get('Config')
        
        meta_use_cls = raw_conf and getattr(raw_conf, '__use_class__', None)
        meta_use_cls and dct.update(__config_class__=meta_use_cls)

        cls: ScopeType[T_Scope, _T_Conf] = super().__new__(mcls, name, bases, dct)

        conf_cls = get_metadata_class(cls, '__config_class__', base=Config, name='Config')
        conf_cls(cls, 'config', raw_conf)
        
        if _INTERNAL_SCOPE_NAMES[cls.config.name]:
            raise NameError(f'Scope: {cls.config.name!r} not allowed')
        elif cls.config.name in _INTERNAL_SCOPE_NAMES:
            _INTERNAL_SCOPE_NAMES[cls.config.name] = not cls._is_abstract()

        cls._is_abstract() or cls._register_scope_type()
        
        return cls
    
    def __repr__(cls) -> str:
        return f'<ScopeType({cls.__name__}, {cls.config!r}>'
    
    def __str__(cls) -> str:
        return f'<ScopeType({cls.__name__}, {cls.config.name!r}>'

    


@export
class Scope(abc.Scope, metaclass=ScopeType[T_Scope, _T_Conf, T_Provider]):
    """"""

    config: ClassVar[_T_Conf]
    __pos: int
    class Config:
        abstract = True

    name: str = _config_lookup()
    embedded: bool = _config_lookup()
    priority: int = _config_lookup()
    context_class: type[T_ContextStack] = _config_lookup()
    injector_class: type[T_Injector] = _config_lookup()
    dependants: KeyedSet[T_Scope]
    injectors: list[ref[T_Injector]]
    _lock: RLock 

    def __init__(self):
        self.__pos = 0
        super().__init__()
        self._lock = RLock()
        self.dependants = KeyedSet()
        self.injectors = []
        signals.boot.send(self.key, scope=self)

    @property
    def is_ready(self):
        return self.__pos > 0

    @property
    def embeds(self):
        return list(s for s in self.depends if s.embedded)

    @cached_property
    def depends(self):
        return dict((d, d) for d in sorted(self._iter_depends()))
          
    @property
    def parents(self):
        return list(s for s in self.depends if not s.embedded)

    @property
    def resolvers(self):
        try:
            return self._resolvers
        except AttributeError:
            return self._make_resolvers()
        finally:
            self.prepare()

    @cached_property
    def providers(self):
        return ChainMap(
                self.__class__.own_providers, 
                *(s.providers for s in reversed(self.embeds)),
            )
           
    @classmethod
    def _implicit_bases(cls):
        return ImplicitScope,

    def bootstrap(self, inj: T_Injector):
        logger.error('    '*(inj.level+1) + f'  >>> bootstrap({self}):  {inj}')
        return

    def create(self, parent: Injector) -> T_Injector:
        if parent and self in parent:
            return parent
            
        for scope in self.parents:
            if not parent or scope not in parent:
                parent = scope.create(parent)


        self.prepare()
        
        rv = self.injector_class(self, parent)
        __debug__ and logger.debug(f'created({self}): {rv!r}')

        self.setup_content(rv)
        self.injectors.append(ref(rv, self.injectors.remove))

        signals.init.send(self.key, injector=rv, scope=self)

        return rv

    def create_context(self, inj: T_Injector) -> T_ContextStack:
        return self.context_class(inj)

    def dispose(self, inj: T_Injector):
        self.injectors.remove(ref(inj))
        inj.content = None
    
    def setup_content(self, inj: T_Injector):
        def fallback(key):
            res = self.providers.get(key)
            if res is None and isinstance(key, ImportRef):
                try:
                    obj = key()
                except Exception:
                    pass
                else:
                    res = self.providers.get(obj)
            
            if res is None:
                return content.setdefault(key, inj.parent.content[key])
            else:
                return content.setdefault(key, res.resolver(self).bind(inj))

        inj.content = content = fallbackdict(fallback)
        return inj    

    def add_dependant(self, scope: T_Scope):
        self.prepare()
        self.dependants.add(scope)
    
    def has_descendant(self, scope: T_Scope):
        self.prepare()
        return scope in self.dependants \
            or any(s.has_descendant(scope) for s in self.dependants)
    
    def flush(self, key: Injectable, *, skip=None):
        if skip is None:
            skip = set()
        elif self in skip:
            return

        skip.add(self)

        if hasattr(self, '_resolvers'):
            if key in self._resolvers:
                del self._resolvers[key]
        for inj in self.injectors:
            if inj := inj():
                del inj[key]

        for d in self.dependants: 
            d.flush(key, skip=skip)


    def prepare(self: T_Scope, *, strict=False):
        if self.is_ready:
            if strict: 
                raise RuntimeError(f'Scope {self} already prepared')
            return
        

        self._prepare()
        self.ready()
        signals.ready.send(self.key, scope=self)
    
    def _prepare(self):
        self.__pos = self.__pos or ordered_id()

        mkprov = partial(AliasProvider, scope=self.name, priority=-1)
        for abstract in (None, Injector, abc.Injector, self.injector_class, INJECTOR_TOKEN):
            self.__class__.register_provider(mkprov(abstract, self))
        
        self.__class__.register_provider(InjectorProvider(self, None, -1, scope=self.name))

        __debug__ and logger.debug(f'prepare({self!r})')

    def _make_resolvers(self):
        def fallback(key):
            pr = self.providers.get(key) 
            return self._resolvers.setdefault(key, pr and pr.resolver( self ))

        self._resolvers = fallbackdict(fallback)
        return self._resolvers

    def _iter_depends(self):
        for scope in map(Scope, self.config.depends):
            scope.add_dependant(self)
            yield scope

    def __contains__(self, x) -> None:
        return x == self or any(True for s in self.depends if x in s)

    def __str__(self) -> str:
        return f'{self.__class__.__name__}[{self.config.name!r}]'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}#{self.config._pos}({self.config.name!r}, '\
            f'#{self.is_ready and self.__pos or ""})'






class ImplicitScope(Scope):
    class Config:
        abstract = True
        implicit = True
        embedded = True
        priority = -1
        





class AnyScope(Scope):
    class Config:
        name = ANY_SCOPE
        embedded = True



class MainScope(Scope):

    __main_inj: T_Injector = None
    class Config:
        name = MAIN_SCOPE

    def create(self, parent: None=None) -> T_Injector:
        try:
            rv = self.injectors[-1]()
        except IndexError:
            rv = None
        finally:
            if rv is None:
                return super().create(None)
            return rv


    


class LocalScope(Scope):

    class Config:
        name = LOCAL_SCOPE
        embedded = True




class CommandScope(Scope):

    class Config:
        name = COMMAND_SCOPE
        depends = [
            MAIN_SCOPE,
            LOCAL_SCOPE,
        ]
        



class RequestScope(Scope):
    class Config:
        name = REQUEST_SCOPE
        depends = [
            MAIN_SCOPE,
            LOCAL_SCOPE,
        ]
        


class TaskScope(Scope):
    class Config:
        name = 'task'
        depends = [
            MAIN_SCOPE,
            LOCAL_SCOPE,
        ]
        















