from abc import ABCMeta
import sys
import typing as t 
import logging
from types import GenericAlias
from weakref import finalize, ref
from functools import cache, partial
from itertools import chain
from collections import ChainMap
from collections.abc import Collection, Callable


from djx.common.abc import Orderable

from djx.common.collections import PriorityStack, fallback_default_dict, nonedict, orderedset, fallbackdict
from djx.common.saferef import SafeReferenceType, SafeRefSet, SafeKeyRefDict
from djx.common.typing import get_origin


from djx.common.utils import ( 
    export, lookup_property, cached_property, cached_class_property, text
)
from djx.common.metadata import metafield, BaseMetadata, get_metadata_class



from .util import unique_id
from .injectors import Injector, InjectorContext
from .common import (
    Injectable, 
    T_Injectable,
    InjectorVar
)

from . import signals

if t.TYPE_CHECKING:
    from . import IocContainer, Provider

logger = logging.getLogger(__name__)




_config_lookup = partial(lookup_property, source='config', read_only=True)



_INTERNAL_SCOPE_NAMES = fallbackdict(main=None, any=None)



ANY_SCOPE = 'any'
MAIN_SCOPE = 'main'
LOCAL_SCOPE = 'local'
REQUEST_SCOPE = 'request'
COMMAND_SCOPE = 'command'
    
export('ANY_SCOPE', 'MAIN_SCOPE', 'LOCAL_SCOPE', 'REQUEST_SCOPE', 'COMMAND_SCOPE')


@export()
class ScopeAlias(GenericAlias):

    __slots__ = ()

    @property
    def name(self):
        return self.__args__[0]

    def __call__(self, *args, **kargs):
        raise TypeError(f"Type {self!r} cannot be instantiated.")

    def __eq__(self, other):
        if isinstance(other, GenericAlias):
            return isinstance(other.__origin__, ScopeType) and self.__args__ == other.__args__
        return NotImplemented

    def __hash__(self):
        return hash((ScopeType, self.__args__))




@export()
class ScopeConfig(BaseMetadata['Scope'], Orderable):

    is_abstract = metafield[bool]('abstract', default=False, inherit=False)

    @metafield[int](inherit=False)
    def _pos(self, value) -> int:
        return unique_id()
    
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
    
    @metafield[type[InjectorContext]](inherit=True)
    def context_class(self, value, base=None):
        return value or base or InjectorContext
    
    @metafield[type[Injector]](inherit=True)
    def injector_class(self, value, base=None):
        return value or base or Injector
    
    @metafield[list[str]](inherit=True)
    def depends(self, value: Collection[str], base=()) -> list[str]:
        _seen = set((self.name,))
        tail = (ANY_SCOPE,)
        self.embedded and _seen.update(tail)

        seen = lambda p: p in _seen or _seen.add(p)
        value = value if value is not None else base or ()
        value = value if self.embedded else chain((v for v in value if v not in tail), tail)
        return [p for p in value if not seen(p)]

    def __order__(self):
        return self.priority, self._pos
        



@export
@Orderable.register
class ScopeType(ABCMeta):
    
    config: ScopeConfig
    Config: type[ScopeConfig]

    __types: t.Final[PriorityStack[str, type['Scope']]] = PriorityStack()

    def __new__(mcls, name, bases, dct) -> 'ScopeType':
        raw_conf = dct.get('Config')
        
        meta_use_cls = raw_conf and getattr(raw_conf, '__use_class__', None)
        meta_use_cls and dct.update(__config_class__=meta_use_cls)

        cls: ScopeType = super().__new__(mcls, name, bases, dct)

        conf_cls = get_metadata_class(cls, '__config_class__', base=ScopeConfig, name='Config')
        cls.config = conf_cls(cls, 'config', raw_conf)
        
        if _INTERNAL_SCOPE_NAMES[cls.config.name]:
            raise NameError(f'Scope: {cls.config.name!r} not allowed')
        elif cls.config.name in _INTERNAL_SCOPE_NAMES:
            _INTERNAL_SCOPE_NAMES[cls.config.name] = not cls._is_abstract()

        cls._is_abstract() or cls._register_scope_type()
        
        return cls

    def _get_scope_name(cls: 'ScopeType', val):
        return val.name if type(val) is ScopeAlias \
            else text.snake(val) if isinstance(val, str)\
            else None if not isinstance(val, ScopeType) or cls._is_abstract(val) \
            else val.config.name

    def _is_abstract(cls: 'ScopeType', val=None):
        return not hasattr(val or cls, 'config') or (val or cls).config.is_abstract

    def _make_implicit_type(cls, name):
        return cls.__class__(name, cls._implicit_bases(), dict())

    def _gettype(cls, name, *, create_implicit=True):
        if name in ScopeType.__types:
            return ScopeType.__types[name]
        elif name and create_implicit:
            return cls._make_implicit_type(name)
        else:
            return cls

    def _active_types(cls):
        return dict(ScopeType.__types)

    def register(cls, subclass: 'ScopeType'):
        super().register(subclass)
        cls._register_scope_type(subclass)
        return subclass

    def _register_scope_type(cls, klass: 'ScopeType' = None):
        klass = klass or cls
        if not cls._is_abstract(klass):
            name = cls._get_scope_name(klass)
            ScopeType.__types[name] = klass
        return cls

    def __order__(cls, self=...):
        return cls.config

    def __repr__(cls) -> str:
        return f'<ScopeType({cls.__name__}, {cls.config!r}>'
    
    def __str__(cls) -> str:
        return f'<ScopeType({cls.__name__}, {cls.config.name!r}>'
        
    __gt__ = Orderable.__gt__
    __ge__ = Orderable.__ge__
    __lt__ = Orderable.__lt__
    __le__ = Orderable.__le__




@export
@Injectable.register
class Scope(Orderable, metaclass=ScopeType):
    """"""

    config: t.ClassVar[ScopeConfig]
    __pos: int
    class Config:
        abstract = True

    name: str = _config_lookup()
    embedded: bool = _config_lookup()
    priority: int = _config_lookup()
    context_class: type[InjectorContext] = _config_lookup()
    injector_class: type[Injector] = _config_lookup()
    dependants: orderedset['Scope']
    injectors: list[ref[Injector]]
    ioc: 'IocContainer'

    # _lock: RLock 
    @classmethod
    @cache
    def __class_getitem__(cls: ScopeType, params=...):
        if params and isinstance(params, tuple):
            param = params[0]
        else:
            param = params

        typ = type(param)
        if typ is ScopeAlias:
            if param.__origin__ is cls:
                return param
            param = param.__args__
        elif issubclass(typ, (ScopeType, str)):
            param = cls._get_scope_name(param)
        elif issubclass(typ, Injector):
            param = param.scope.name
        elif isinstance(typ, ScopeType):
            param = cls._get_scope_name(param.__class__)
        elif param in (..., (...,), [...], t.Any, (t.Any,),[t.Any], (), []):
            param = ANY_SCOPE  

        return ScopeAlias(cls, param)

    def __init__(self, ioc: 'IocContainer'):
        self.__pos = 0
        # self._lock = RLock()
        self.ioc = ioc
        self.dependants = orderedset()
        self.injectors = []
        self.boot()

    @cached_class_property
    def key(cls):
        return cls[cls.config.name] if not cls._is_abstract() else cls

    def ready(self) -> None:
        ...
    
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

    # def aka(self, *aliases):
    #     aka = self.aliases
    #     if aliases:
    #         return next((True for a in aliases if a in aka), False)
    #     return len(aka) > 1

    def is_provided(self, 
                    obj: Injectable,
                    *, 
                    start: t.Union[str, ScopeAlias]=..., 
                    stop: t.Union[str, ScopeAlias]=..., 
                    depth: int=sys.maxsize):
        return self.find_provider(obj, start=start, stop=stop, depth=depth) is not None

    def boot(self):
        self.ioc.scope_booted(self)

    def find_provider(self, 
                    key: Injectable, 
                    *,
                    start: t.Union[str, ScopeAlias]=..., 
                    stop: t.Union[str, ScopeAlias]=..., 
                    depth: int=sys.maxsize) -> t.Union['Provider', None]:

        this = self

        if start and start is not ...:
            start = self.ioc.scopekey(start)
            if start not in this:
                return None
                
            while not (start == this or start in this.embeds):
                if this.parent is None:
                    return None
                this = this.parent 
        

        if res := this.providers.get(key):
            return res
        elif res := this.providers.get(get_origin(key)):
            if res.can_provide(this, key):
                return res
        
        if not(depth > 0 and this.parent):
            return None
        elif stop and stop is not ...:
            end_scope = self.ioc.scopekey(stop)
            if end_scope == this or end_scope in this.embeds:
                return None
        return this.parent.find_provider(key, stop=stop, depth=depth-1)

    def register_dependency(self, dep: Injectable, *sources: Injectable):
        if sources:
            deps = self._linked_deps
            for src in sources:
                deps[src].add(dep)

    def create(self, parent: Injector) -> Injector:
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
        # __debug__ and logger.debug(f'created({self}): {rv!r}')

        self.setup_injector_vars(rv)
        wrv = ref(rv)
        self.injectors.append(wrv)
        finalize(rv, self._remove_injector, wrv, rv.name)
        signals.init.send(self.key, injector=rv, scope=self)

        return rv

    def create_context(self, inj: Injector) -> InjectorContext:
        return self.context_class(inj)

    def _remove_injector(self, inj, name=None) -> InjectorContext:
        return self.injectors.remove(inj)

    def dispose(self, inj: Injector):
        self.injectors.remove(ref(inj))
        inj.vars = None
    
    def setup_injector_vars(self, inj: Injector):
        resolvers: Callable[..., 'InjectorVar'] = self.resolvers
        def fallback(token):
            nonlocal resolvers, setdefault, inj, parent
            res = resolvers[token]
            if res is None:
                return setdefault(token, parent[token]) 
            return setdefault(token, res(inj))
            
        inj.vars = fallbackdict(fallback)
        setdefault = inj.vars.setdefault
        parent = inj.parent.vars
        return inj

    def add_dependant(self, scope: 'Scope'):
        self.prepare()
        self.dependants.add(scope)
    
    def has_descendant(self, scope: 'Scope'):
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

    def prepare(self: 'Scope', *, strict=False):
        if self.is_ready:
            if strict: 
                raise RuntimeError(f'Scope {self} already prepared')
            return
        self._prepare()
        self.ready()
        self.ioc.scope_ready(self)

    def _prepare(self):
        self.__pos = self.__pos or unique_id()
        self.ioc.alias(self, Injector, at=self.name, priority=-10)
        __debug__ and logger.debug(f'prepare({self!r})')

    def _make_resolvers(self):
        if self.embedded:
            return nonedict()

        get_provider: Callable[..., 'Provider'] = self.providers.get

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
                isinstance(x, (Scope, ScopeType, ScopeAlias)) 
                and any(x in s for s in self.depends)
            )

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.name!r})'

    __str__ = __repr__

    @classmethod
    def __order__(cls, self=...):
        return cls.config
       
    def __eq__(self, x, orderby=None) -> bool:
        if isinstance(x, ScopeAlias):
            return x == self.key
        elif isinstance(x, (Scope, ScopeType)):
            return x.key == self.key
        # elif isinstance(x, Injector):
        #     return x == self.key
        else:
            return False

    def __hash__(self) -> int:
        return hash(self.key)






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

    def create(self, parent: None=None) -> Injector:
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
        












