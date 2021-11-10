import sys
import typing as t 
import logging
from operator import index
from threading import RLock
from types import GenericAlias
from weakref import finalize, ref
from functools import partial
from itertools import chain
from collections import ChainMap
from collections.abc import Collection, Callable
from django.db.models.query_utils import Q

from djx.common.collections import fallback_default_dict, nonedict, orderedset, fallbackdict
from djx.common.imports import ImportRef
from djx.common.saferef import SafeReferenceType, SafeRefSet, SafeKeyRefDict
from djx.common.typing import GenericLike, get_origin


from djx.common.utils import export, lookup_property, cached_property, noop
from djx.common.metadata import metafield, BaseMetadata, get_metadata_class
from djx.common.utils.data import setdefault



from .inspect import ordered_id
from .injectors import Injector, InjectorContext, NullInjector, INJECTOR_TOKEN
from .abc import (
    ANY_SCOPE, COMMAND_SCOPE, LOCAL_SCOPE, MAIN_SCOPE, REQUEST_SCOPE,
    Injectable, ScopeConfig, 
    T_ContextStack, T_Injector, T_Injectable, T_Provider, _T_Conf,
)

from . import abc, signals

if t.TYPE_CHECKING:
    from . import IocContainer, Provider

logger = logging.getLogger(__name__)


T_Scope = t.TypeVar('T_Scope', bound='Scope')


_config_lookup = partial(lookup_property, source='config', read_only=True)



_INTERNAL_SCOPE_NAMES = fallbackdict(main=None, any=None)

@export()
class Config(BaseMetadata[T_Scope], ScopeConfig, t.Generic[T_Scope, T_Injector, T_ContextStack]):

    is_abstract = metafield[bool]('abstract', default=False, inherit=False)

    @metafield[int](inherit=False)
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
    # __instance__: T_Scope

    def __new__(mcls, name, bases, dct) -> 'ScopeType[T_Scope]':
        raw_conf = dct.get('Config')
        
        meta_use_cls = raw_conf and getattr(raw_conf, '__use_class__', None)
        meta_use_cls and dct.update(__config_class__=meta_use_cls)

        cls: ScopeType[T_Scope, _T_Conf] = super().__new__(mcls, name, bases, dct)

        conf_cls = get_metadata_class(cls, '__config_class__', base=Config, name='Config')
        cls.config = conf_cls(cls, 'config', raw_conf)
        
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

    config: t.ClassVar[_T_Conf]
    __pos: int
    class Config:
        abstract = True

    name: str = _config_lookup()
    embedded: bool = _config_lookup()
    priority: int = _config_lookup()
    context_class: type[T_ContextStack] = _config_lookup()
    injector_class: type[T_Injector] = _config_lookup()
    dependants: orderedset[T_Scope]
    injectors: list[ref[T_Injector]]
    ioc: 'IocContainer'

    # _lock: RLock 

    def __init__(self, ioc: 'IocContainer'):
        self.__pos = 0
        # self._lock = RLock()
        self.ioc = ioc
        self.dependants = orderedset()
        self.injectors = []
        self.boot()

    @property
    def is_ready(self):
        return self.__pos > 0

    @property
    def embeds(self) -> orderedset['Scope']:
        return orderedset(s for s in self.depends if s.embedded)

    @cached_property
    def depends(self) -> orderedset['Scope']:
        return orderedset(sorted(self._iter_depends()))
          
    @cached_property
    def aliases(self):
        return orderedset(self.ioc.get_scope_aliases(self))
          
    @cached_property
    def _linked_deps(self) -> dict[SafeReferenceType[T_Injectable], SafeRefSet[T_Injectable]]:
        return SafeKeyRefDict.using(lambda: fallback_default_dict(SafeRefSet))()

    @cached_property
    def parent(self):
        return next((s for s in self.depends if not s.embedded), None)

    @property
    def resolvers(self):
        try:
            return self._resolvers
        except AttributeError:
            self._resolvers = self._make_resolvers()
            return self._resolvers

    @cached_property
    def providers(self) -> ChainMap[T_Injectable, 'Provider']:
        return ChainMap(
                self.ioc.providers[self.name], 
                *(s.providers for s in reversed(self.embeds)),
            )

    # @cached_property
    # def aliased(self) -> ChainMap[T_Injectable, T_Provider]:
    #     return 
           
    @classmethod
    def _implicit_bases(cls):
        return ImplicitScope,

    def aka(self, *aliases):
        aka = self.aliases
        if aliases:
            return next((True for a in aliases if a in aka), False)
        return len(aka) > 1

    def boot(self):
        self.ioc.scope_booted(self)

    def boot(self):
        self.ioc.scope_booted(self)

    # def bootstrap(self, inj: T_Injector):
    #     logger.error('    '*(inj.level+1) + f'  >>> bootstrap({self}):  {inj}')
    #     return

    def find_provider(self, key, *, stop: t.Union[str, abc.ScopeAlias]=..., depth: int=sys.maxsize) -> t.Union['Provider', None]:
        if res := self.providers.get(key):
            return res
        elif not(depth > 0 and self.parent):
            return None
        elif stop is not ...:
            scope = Scope[stop]
            if scope == self or scope in self.embeds:
                return None
        return self.parent.find_provider(key, stop=stop, depth=depth-1)

    def register_dependency(self, dep: Injectable, *sources: Injectable):
        if sources:
            deps = self._linked_deps
            for src in sources:
                deps[src].add(dep)

    def create(self, parent: Injector) -> T_Injector:
        prt = self.parent
        if (parent and parent.scope) != prt:
            if prt and (not parent or parent.scope in prt):
                parent = prt.create(parent)
            else:
                raise ValueError(
                    f'Error creating Injector. Invalid parent injector {parent=} '
                    f'from {parent.scope=}. Expected {prt!r}.'
                )

        if not self.is_ready:
            self.prepare()
        
        rv = self.injector_class(self, parent)
        __debug__ and logger.debug(f'created({self}): {rv!r}')

        self.setup_content(rv)
        wrv = ref(rv)
        self.injectors.append(wrv)
        finalize(rv, self._remove_injector, wrv, rv.name)
        signals.init.send(self.key, injector=rv, scope=self)

        return rv

    def create_context(self, inj: T_Injector) -> T_ContextStack:
        return self.context_class(inj)

    def _remove_injector(self, inj, name=None) -> T_ContextStack:
        return self.injectors.remove(inj)

    def dispose(self, inj: T_Injector):
        self.injectors.remove(ref(inj))
        inj.content = None
    
    def setup_content(self, inj: T_Injector):
        get_resolver: Callable[..., abc.InjectorVar] = self.resolvers.__getitem__
        def fallback(token):
            res = get_resolver(token)
            if res is None:
                return setdefault(token, inj.parent.content[token])
            else:
                return setdefault(token, res(inj))

        inj.content = fallbackdict(fallback)
        setdefault = inj.content.setdefault
        return inj

    def add_dependant(self, scope: T_Scope):
        self.prepare()
        self.dependants.add(scope)
    
    def has_descendant(self, scope: T_Scope):
        self.prepare()
        return scope in self.dependants \
            or any(s.has_descendant(scope) for s in self.dependants)
    
    def flush(self, key: Injectable, *, _target: 'Scope'=..., _skip: orderedset=None):
        sk = self, key

        if _skip is None: 
            _skip = orderedset()
        elif sk in _skip:
            return

        _skip.add(sk)
        
        for inj in self.injectors:
            if inj := inj():
                del inj[key]
        
        if not self.embedded:
            if linked := self._linked_deps.pop(key, None):
                for dep in linked:
                    self.flush(dep, _skip=_skip)
    
            self.resolvers.pop(key, None)
                    
        for d in self.dependants: 
            d.flush(key, _skip=_skip)

    def prepare(self: T_Scope, *, strict=False):
        if self.is_ready:
            if strict: 
                raise RuntimeError(f'Scope {self} already prepared')
            return
        self._prepare()
        self.ready()
        self.ioc.scope_ready(self)

    def _prepare(self):
        self.__pos = self.__pos or ordered_id()
        self.ioc.alias(self, abc.Injector, at=self.name, priority=-10)
        __debug__ and logger.debug(f'prepare({self!r})')

    def _make_resolvers(self):
        if self.embedded:
            return nonedict()

        get_provider: Callable[..., abc.Provider] = self.providers.get

        def fallback(key):
            if pro := get_provider(key):
                return setdefault(key, pro(self, key))
            elif origin := get_origin(key):
                if pro := get_provider(origin):
                    return setdefault(key, pro(self, key))
            # return setdefault(key, None)

        res = fallbackdict(fallback)
        setdefault = res.setdefault
        return res

    def _iter_depends(self):
        ioc = self.ioc
        
        parents = []

        for s in self.config.depends:
            scope = ioc.scopes[s]
            if not scope.embedded:
                parents.append(scope)
                if len(parents) > 1:
                    continue

            scope.add_dependant(self)
            yield scope
        
        if parents:
            if len(parents) > 1:
                raise ValueError(
                    f'scopes can only depend on 1 standalone parent.' 
                    f'{self} depends on {", ".join(map(str, parents))}')
            self.parent = parents[0]

    def __contains__(self, x) -> bool:
        return x == self \
            or x in self.depends \
            or (
                isinstance(x, (abc.Scope, abc.ScopeType, abc.ScopeAlias)) 
                and any(x in s for s in self.depends)
            )

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}[{self.name!r}]'

    __str__ = __repr__

    # def __str__(self) -> str:
    #     return f'{self.__class__.__name__}({self.config.name!r}, #{self.config._pos})'
            






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

    class Config:
        name = MAIN_SCOPE

    def create(self, parent: None=None) -> T_Injector:
        try:
            rv = self.injectors[-1]()
        except IndexError:
            rv = None
        finally:
            if rv is None:
                return super().create(parent)
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
        












