from contextvars import ContextVar, Token
import sys
import typing as t 
import logging
from weakref import finalize, ref
from collections import ChainMap
from collections.abc import Mapping, Callable, Sequence, Generator
from build import Mapping


from laza.common.collections import fallback_default_dict, nonedict, orderedset, fallbackdict
from laza.common.saferef import SafeReferenceType, SafeRefSet, SafeKeyRefDict
from laza.common.typing import get_origin


from laza.common.functools import ( 
    export, cached_property
)



from .new_injectors import Injector, InjectorContext
from .common import (
    Injectable, 
    T_Injectable,
)

from . import signals
from . import new_providers as p
from .new_container import IocContainer, AbcIocContainer


logger = logging.getLogger(__name__)





@export
class AbcScope(AbcIocContainer):
    """"""

    name: str
    root: 'AbcScope'
    parent: 'AbcScope'
    injectors: dict[Injector, t.Union[Token, None]]

    shared: bool = True
    injector_class: type[Injector] = Injector

    def __init__(self, 
                name: str,
                parent: 'AbcScope',
                *requires: 'IocContainer', 
                injector_class: type[Injector]=None):
        self.set_parent(parent)
        super().__init__(*requires, name=name, shared=True)
        self.injectors = dict()

        if injector_class is not None:
            self.injector_class = injector_class
  
    @cached_property
    def containers(self) -> orderedset[IocContainer]:
        return orderedset(self._create_containers())
    
    @cached_property
    def repository(self) -> Mapping[T_Injectable, p.Provider]:
        return self._create_repository()
    
    @cached_property
    def resolvers(self):
        return self._create_resolvers()

    @cached_property
    def _linked_deps(self) -> dict[SafeReferenceType[T_Injectable], SafeRefSet[T_Injectable]]:
        return SafeKeyRefDict.using(lambda: fallback_default_dict(SafeRefSet))()

    def set_parent(self, parent: 'AbcScope'=None):
        if hasattr(self, 'parent'):
            raise AttributeError(f'{self.__class__.__name__}.parent already set.')

        if parent is None:
            self.parent = parent
            self.root = self
        elif isinstance(parent, AbcScope):
            self.parent = parent
            self.root = parent.root
            parent.add_dependant(self)
        else:
            raise ValueError(
                f'{parent.__class__.__qualname__!r}. '
                f'{self.__class__.__name__}.parent must be Scope or NoneType.'
            )
        return self

    def _create_repository(self):
        return ChainMap(self.registry, *(d.registry for d in self.containers))

    def _create_resolvers(self):
       
        get_provider: Callable[..., p.Provider] = self.repository.get

        def fallback(key):
            if pro := get_provider(key):
                func, deps = pro._provide(self, key)
                if setdefault(key, func) is func:
                    if func is not None and deps:
                        self.register_dependency(key, *deps)
                return func
            elif origin := get_origin(key):
                if pro := get_provider(origin):
                    func, deps = pro._provide(self, key)
                    if setdefault(key, func) is func:
                        if func is not None and deps:
                            self.register_dependency(key, *deps)
                    return func

        res = fallbackdict(fallback)
        setdefault = res.setdefault
        return res

    def _expand_requirements(self, src: IocContainer=None, *, memo_=None):
        if memo_ is None:
           memo_ = set()

        if src is None:
            src = self

        for d in src.requires:
            if d in memo_ or memo_.add(d):
                continue

            yield from t.cast(Sequence[tuple[IocContainer, IocContainer]], self._expand_requirements(d, memo_=memo_))
            yield src, d

    def _create_containers(self):
        parent = self.parent or ()
        return orderedset(
            yv for s, d in self._expand_requirements()
            if not(d.shared and d in parent) and (yv := d.add_dependant(self))
        )
          
    def _setup_requires(self):
        self.requires = orderedset()
     
    def _setup_dependants(self):
        self.dependants = orderedset()

    def is_provided(self, 
                    obj: Injectable,
                    *, 
                    start: IocContainer=..., 
                    stop: IocContainer=..., 
                    depth: int=sys.maxsize):
        return self.find_provider(obj, start=start, stop=stop, depth=depth) is not None

    def find_provider(self, 
                    key: Injectable, 
                    *,
                    start: IocContainer=..., 
                    stop: IocContainer=..., 
                    depth: int=sys.maxsize) -> t.Union[p.Provider, None]:

        this = self

        if start and start is not ...:
            if start not in this:
                return None

            while not (start is this or start in this.requires):
                if this.parent is None:
                    return None
                this = this.parent 
        
        if res := this[key]:
            return res
        elif res := this[get_origin(key)]:
            if res.can_provide(this, key):
                return res
        
        if not(depth > 0 and this.parent):
            return None
        elif stop and stop is not ...:
            if stop is this or stop in this.requires:
                return None
        return this.parent.find_provider(key, stop=stop, depth=depth-1)

    def register_dependency(self, dep: Injectable, *sources: Injectable):
        if sources:
            deps = self._linked_deps
            for src in sources:
                deps[src].add(dep)

    def make(self, parent: Injector=None) -> Injector:
        prt = self.parent
        if (parent and parent.scope) != prt:
            if prt and (not parent or parent.scope in prt):
                parent = prt.make(parent)
            else:
                raise ValueError(
                    f'Error creating Injector. Invalid parent injector {parent=} '
                    f'from {parent.scope=}. Expected {prt!r}.'
                )
        self.repository
        rv = self.injector_class(self, parent)
        return rv

    def dispatch_injector(self, inj: Injector):
        ctx = self._context
        cur = ctx.get()

        if cur and self in cur.scope:
            self.injectors[inj] = None
        else:
            self.injectors[inj] = ctx.set(inj)
        # self.setup_injector_vars(inj)

    def dispose_injector(self, inj: Injector):
        token = self.injectors.pop(inj)
        if token is not None:
            self._context.reset(token)
        # self.teardown_injector_vars(inj)

    def setup_injector_vars(self, inj: Injector):
        resolvers = self.resolvers
        def fallback(token):
            nonlocal resolvers, setdefault, inj, parent
            res = resolvers[token]
            if res is None:
                return setdefault(token, parent.vars[token]) 
            return setdefault(token, res(inj))
            
        inj.vars = fallbackdict(fallback)
        setdefault = inj.vars.setdefault
        parent = inj.parent
        return inj

    def teardown_injector_vars(self, inj: Injector):
        inj.vars = None

    def add_dependant(self, scope: 'AbcScope'):
        if not isinstance(scope, AbcScope):
            raise TypeError(
                f'{scope.__class__.__qualname__} cannot be a '
                f'{self.__class__.__name__} dependant.'
            )
        return super().add_dependant(scope)
  
    def flush(self, key: Injectable, source=None, *, skip_: orderedset=None):
        sk = self, key

        if skip_ is None: 
            skip_ = orderedset()
        elif sk in skip_:
            return

        skip_.add(sk)
        
        for inj in self.injectors:
            del inj.vars[key]
        
        if linked := self._linked_deps.pop(key, None):
            for dep in linked:
                self.flush(dep, skip_=skip_)

        self.resolvers.pop(key, None)
                    
        for d in self.dependants: 
            d.flush(key, source or self, _skip=skip_)



    def __contains__(self, x):
        if isinstance(x, IocContainer):
            return x in self.requires \
                or any(x in d for d in self.requires) \
                or x.shared and x in (self.parent or ())
        elif isinstance(x, AbcScope):
            return x is self \
                or x in (self.parent or ())
        else:
            return super().__contains__(x)
  
    def __str__(self) -> str:
        parent = self.parent
        return f'{self.__class__.__name__}({self.name!r}, {parent=!s})'

    def __repr__(self) -> str:
        parent = self.parent
        containers = [*self.containers]
        return f'{self.__class__.__name__}({self.name!r}, {containers=!r}, {parent=!r})'





@export
class MainScope(AbcScope):
    
    _context = None

    def __init__(self, 
                *requires: 'IocContainer', 
                name: str='main',
                context: InjectorContext=None):
        super().__init__(name, None, *requires)
        self._context = context or InjectorContext(f'{self.name}.injector', default=None)




@export
class LocalScope(AbcScope):
    
    _context = None
    
    def __init__(self, 
                parent: 'AbcScope',
                *requires: 'IocContainer', 
                name: str='local'):
        super().__init__(name, parent, *requires)
        self._context = self.parent._context
