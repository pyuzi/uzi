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
from laza.common.typing import get_origin, Self
from laza.common.proxy import proxy

from laza.common.functools import ( 
    export, cached_property
)



from .vars import NullScope, Scope
from .common import (
    Injectable, 
    T_Injectable,
)

from . import providers as p
from .containers import IocContainer, AbcIocContainer


logger = logging.getLogger(__name__)

_D = t.TypeVar("_D")
_T_Scope = t.TypeVar('_T_Scope', bound=Scope)


_ioc_local = IocContainer(shared=False)
_ioc_main = IocContainer(_ioc_local)





class InjectorContext(t.Protocol[_T_Scope]):
    
    def __init__(self, name: str, *, default: _T_Scope = ...) -> None: ...
    @property
    def name(self) -> str: ...
    @t.overload
    def get(self) -> _T_Scope: ...
    @t.overload
    def get(self, default: t.Union[_T_Scope, _D]) -> t.Union[_T_Scope, _D]: ...
    def set(self, value: _T_Scope) -> Token[_T_Scope]: ...
    def reset(self, token: Token[_T_Scope]) -> None: ...
   
   


@export
class Injector(p.RegistrarMixin):
    """"""

    name: str
    parent: 'Injector'
    children: orderedset['Injector']
    scopes: dict[Scope, t.Union[Token, None]]

    scope_class: type[Scope] = Scope
    scope_context_class: type[InjectorContext] = ContextVar
    _checkouts: t.Final[int] 

    container: IocContainer
    __truectx: InjectorContext
    _context: Scope

    def __init__(self, 
                name: str,
                parent: 'Injector',
                *requires: 'IocContainer', 
                container: IocContainer=None,
                children: Sequence['Injector']=None,
                context: InjectorContext=None,
                scope_class: type[Scope]=None,
                context_class: type[InjectorContext] =None):

        self.scopes = dict()
        self.children = orderedset(children or ())
        self._checkouts = 0

        self.name = name

        if scope_class is not None:
            self.scope_class = scope_class
  
        if context_class is not None:
            self.scope_context_class = context_class
        
        self.container = container or IocContainer(name=self.name)

        self.set_parent(parent)

        requires and self.container.require(*requires)

        if context is not None:
            self.setup(context)

    @property
    def has_setup(self):
        return 

    @cached_property
    def containers(self) -> orderedset[IocContainer]:
        return orderedset(self._create_containers())
    
    @cached_property
    def _registry(self) -> Mapping[T_Injectable, p.Provider]:
        return self._create_registry()
    
    @cached_property
    def _bindings(self):
        return self._create_bindings()

    @cached_property
    def _linked_deps(self) -> dict[SafeReferenceType[T_Injectable], SafeRefSet[T_Injectable]]:
        return SafeKeyRefDict.using(lambda: fallback_default_dict(SafeRefSet))()

    def set_parent(self, parent: 'Injector'=None):
        if hasattr(self, 'parent'):
            raise AttributeError(f'{self.__class__.__name__}.parent already set.')

        parent and parent.add_child(self)
        self.parent = parent

        return self
    
    def add_child(self, child: 'Injector'):
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
                self.__truectx = self.scope_context_class(self.name, default=NullScope())
                ctx = self.__truectx.get
            
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

    def register_provider(self, provider: p.Provider) -> Self:
        self.container.register_provider(provider)
        return self

    def _create_registry(self):
        return ChainMap(*(d._registry for d in self.containers))

    def _expand_requirements(self, src: IocContainer=None, *, memo_=None):
        if memo_ is None:
           memo_ = set()

        if src is None:
            src = self.container
            yield self, src

        for d in src._requires:
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

            while not (start is this or start in this._requires):
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
            if stop is this or stop in this._requires:
                return None
        return this.parent.find_provider(key, stop=stop, depth=depth-1)

    # def register_handler(self, dep: Injectable, handler: p.Handler, deps: Sequence[Injectable]=None):
    #     if deps is None:
    #         deps = getattr(handler, 'deps', None) 

    #     if deps:
    #         graph = self._linked_deps
    #         for src in deps:
    #             graph[src].add(dep)
    #     return handler

    def make(self, parent: Scope=None) -> Scope:
        prt = self.parent
        if (parent and parent.injector) != prt:
            if prt and (not parent or parent.injector in prt):
                parent = prt.make(parent)
            else:
                raise ValueError(
                    f'Error creating Injector. Invalid parent injector {parent=} '
                    f'from {parent.injector=}. Expected {prt!r}.'
                )
        rv = self.scope_class(self, parent)
        return rv

    def dispatch_scope(self, scope: Scope, *stack: Scope):
        
        if scope in self.scopes:
            raise RuntimeError(f'Scope {scope} already dispated')

        self.scopes[scope] = None if stack else self._push_scope(scope)
        self.setup_scope(scope)

    def _push_scope(self, scope: Scope):
        while self.parent:
            self = self.parent
        return self.__truectx.set(scope)

    def _pop_scope(self, token: Token):
        while self.parent:
            self = self.parent
        return self.__truectx.reset(token)

    def dispose_scope(self, scope: Scope, child: Scope=None):
        self.teardown_scope(scope)
        token = self.scopes.pop(scope)
        if token is not None:
            self._pop_scope(token)

    def setup_scope(self, scope: Scope):
        scope.bindings = self._bindings

    def teardown_scope(self, scope: Scope):
        scope.bindings = None

    def add_dependant(self, scope: 'Injector'):
        if not isinstance(scope, Injector):
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
        
        for scope in self.scopes:
            del scope.vars[key]
        
        if linked := self._linked_deps.pop(key, None):
            for dep in linked:
                self.flush(dep, skip_=skip_)

        self._bindings.pop(key, None)
                    
        for d in self.children: 
            d.flush(key, source or self, _skip=skip_)

    def __contains__(self, x):
        if isinstance(x, IocContainer):
            return x in self._requires \
                or any(x in d for d in self._requires) \
                or x.shared and x in (self.parent or ())
        elif isinstance(x, Injector):
            return x is self \
                or x in (self.parent or ())
        else:
            return x in self._registry\
                or x in (self.parent or ())
    
    def __del__(self):
        self.teardown()
       
    def __str__(self) -> str:
        parent = self.parent
        return f'{self.__class__.__name__}({self.name!r}, {parent=!s})'

    def __repr__(self) -> str:
        parent = self.parent
        containers = [*self.containers]
        return f'{self.__class__.__name__}({self.name!r}, {containers=!r}, {parent=!r})'

    def _create_bindings(self):
       
        get_provider = self._registry.get

        def fallback(key):
            if pro := get_provider(key):
                return setdefault(key, pro.bind(self, key))
            elif origin := get_origin(key):
                if pro := get_provider(origin):
                    return setdefault(key, pro.bind(self, key))

        res = fallbackdict(fallback)
        setdefault = res.setdefault
        return res

    # def _register_handler(self, dep: Injectable, handler, deps: Sequence[Injectable]=None):
    #     if deps is None:
    #         deps = getattr(handler, 'deps', None) 

    #     if deps:
    #         graph = self._linked_deps
    #         for src in deps:
    #             graph[src].add(dep)
    #     return handler




@export
class MainInjector(Injector):
    
    _context = None
    _default_requires = _ioc_main,

    def __init__(self, 
                *requires: 'IocContainer', 
                name: str='main',
                context: InjectorContext=None,
                scope_class: type[Scope]=None,
                context_class: type[InjectorContext] =None):
        super().__init__(
                name, None, 
                *requires, 
                context=context,
                scope_class=scope_class, 
                context_class=context_class,
            )
    
    def dispatch_scope(self, scope: Scope, *stack: Scope):
        self.setup()
        super().dispatch_scope(scope, *stack)

    def dispose_scope(self, scope: Scope, *stack: Scope):
        super().dispose_scope(scope, *stack)
        self.teardown()



@export
class LocalInjector(Injector):
    
    _context = None
    _default_requires = _ioc_local,
    
    def __init__(self, 
                parent: 'Injector',
                *requires: 'IocContainer', 
                name: str='local',
                scope_class: type[Scope]=None):

        super().__init__(
                name, parent, 
                *requires, 
                scope_class=scope_class
            )
