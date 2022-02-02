from abc import abstractmethod
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



from .injectors import Injector, InjectorContext, InjectorVarDict
from .common import (
    Injectable, 
    T_Injectable,
)

from . import providers as p
from .containers import IocContainer, AbcIocContainer


logger = logging.getLogger(__name__)


_T_Scope = t.TypeVar('_T_Scope', bound='AbcScope', covariant=True)


_ioc_local = IocContainer(shared=False)
_ioc_main = IocContainer(_ioc_local)



@export
class AbcScope(AbcIocContainer):
    """"""

    name: str
    parent: 'AbcScope'
    children: orderedset['AbcScope']
    injectors: dict[Injector, t.Union[Token, None]]

    shared: bool = True
    injector_class: type[Injector] = Injector
    injector_context_class: type[InjectorContext] = ContextVar
    injectorvar_dict_class: type[InjectorVarDict] = InjectorVarDict
    _checkouts: t.Final[int] 

    def __init__(self, 
                name: str,
                parent: 'AbcScope',
                *requires: 'IocContainer', 
                children: Sequence['AbcScope']=None,
                context: InjectorContext=None,
                injector_class: type[Injector]=None,
                context_class: type[InjectorContext] =None,
                injectorvar_dict_class: type[InjectorVarDict]=None):

        self.set_parent(parent)

        super().__init__(*requires, name=name, shared=True)

        self.injectors = dict()
        self.children = orderedset(children or ())
        self._checkouts = 0

        if injector_class is not None:
            self.injector_class = injector_class
  
        if injectorvar_dict_class is not None:
            self.injectorvar_dict_class = injectorvar_dict_class
    
        if context_class is not None:
            self.injector_context_class = context_class
        
        if context is not None:
            self.setup(context)

        # self._context = context \
        #     or (self.parent and self.parent._context) \
        #     or (self.injector_context_class(f'{self.name}.injector', default=None))
    
    @property
    def has_setup(self):
        return 

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

        parent and parent.add_child(self)
        self.parent = parent

        return self
    
    def add_child(self, child: 'AbcScope'):
        if child in self.children or self.children.add(child):
            return False
        elif self.has_setup:
            child.setup(self._context)
        return True

    def setup(self, ctx: 'InjectorContext'=None):
        old = self._context 
        if old is None:
            if ctx is not None:
                pass
            elif self.parent:
                return self.parent.setup()
            else:
                ctx = self.injector_context_class(f'{self.name}.injector', default=None)
            
            self._context = ctx
            for ls in (self.containers, self.children):
                for c in ls:
                    c.setup(ctx)
        elif old is (ctx or old):
            raise RuntimeError(f'{self!s} already setup')

        self._checkouts += 1
        return self._checkouts == 1

    def teardown(self, ctx=None) -> t.NoReturn:

        if self._checkouts == 1:
            self._checkouts -= 1
            old = self._context
            if ctx is None:
                ctx = old
            elif old is not ctx:
                raise RuntimeError(f'invalid teardown context in {self!s}.')

            if old is not None:
                self._context = None
                for ls in (self.containers, self.children):
                    for c in ls:
                        c.teardown(ctx)
                return True
        elif self._checkouts > 1:
            self._checkouts -= 1
        elif self._checkouts < 0:
            raise RuntimeError(f'too many teardowns {self!s}.')

        return False
        
                        
    def _create_repository(self):
        return ChainMap(self.registry, *(d.registry for d in self.containers))

    def _create_resolvers(self):
       
        get_provider: Callable[..., p.Provider] = self.repository.get

        def fallback(key):
            if pro := get_provider(key):
                hand = pro._handler(self, key)
                return setdefault(key, self.register_handler(key, hand))
            elif origin := get_origin(key):
                if pro := get_provider(origin):
                    hand = pro._handler(self, key)
                    return setdefault(key, self.register_handler(key, hand))

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
    
    def _setup_dependants(self):
        pass

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

    def register_handler(self, dep: Injectable, handler: p.Handler, deps: Sequence[Injectable]=None):
        if deps is None:
            deps = getattr(handler, 'deps', None) 

        if deps:
            graph = self._linked_deps
            for src in deps:
                graph[src].add(dep)
        return handler

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
        rv = self.injector_class(self, parent)
        return rv

    def dispatch_injector(self, inj: Injector, child: Injector=None):
        token = None
        if child is None:
            ctx = self._context
            token = ctx.set(inj)
        
        self.injectors[inj] = token
        self.setup_injector_vars(inj)

    def dispose_injector(self, inj: Injector, child: Injector=None):
        token = self.injectors.pop(inj)
        if token is not None:
            self._context.reset(token)
        self.teardown_injector_vars(inj)

    def setup_injector_vars(self, inj: Injector):
        inj.vars = self.injectorvar_dict_class(inj)

    def teardown_injector_vars(self, inj: Injector):
        inj.vars = None

    def add_dependant(self, scope: 'AbcScope'):
        if not isinstance(scope, AbcScope):
            raise TypeError(
                f'{scope.__class__.__qualname__} cannot be a '
                f'{self.__class__.__name__} dependant.'
            )
        if scope._context not in (self._context, None):
            raise ValueError(
                f'InjectorContext conflict in {self} '
                f'{self._context=} and {scope._context}'
            )

        self.dependants.add(scope)


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
                    
        for d in self.children: 
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
    
    def __del__(self):
        self.teardown()
       
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
    _default_requires = _ioc_main,

    def __init__(self, 
                *requires: 'IocContainer', 
                name: str='main',
                context: InjectorContext=None,
                injector_class: type[Injector]=None,
                context_class: type[InjectorContext] =None,
                injectorvar_dict_class: type[InjectorVarDict]=None):
        super().__init__(
                name, None, 
                *requires, 
                context=context,
                injector_class=injector_class, 
                context_class=context_class,
                injectorvar_dict_class=injectorvar_dict_class
            )
    
    def dispatch_injector(self, inj: Injector, child: Injector=None):
        self.setup()
        super().dispatch_injector(inj, child)

    def dispose_injector(self, inj: Injector, child: Injector=None):
        super().dispose_injector(inj, child)
        self.teardown()



@export
class LocalScope(AbcScope):
    
    _context = None
    _default_requires = _ioc_local,
    
    def __init__(self, 
                parent: 'AbcScope',
                *requires: 'IocContainer', 
                name: str='local',
                injector_class: type[Injector]=None,
                injectorvar_dict_class: type[InjectorVarDict]=None):
        super().__init__(
                name, parent, 
                *requires, 
                injector_class=injector_class, 
                injectorvar_dict_class=injectorvar_dict_class
            )
