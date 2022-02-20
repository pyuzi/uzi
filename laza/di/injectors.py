from abc import abstractmethod
from contextvars import ContextVar, Token
import sys
import typing as t 
import logging
from weakref import finalize, ref
from collections.abc import Mapping, Callable, Sequence, Generator
from build import Mapping


from laza.common.collections import MultiChainMap, fallback_default_dict, nonedict, orderedset, fallbackdict
from laza.common.saferef import SafeReferenceType, SafeRefSet, SafeKeyRefDict
from laza.common.typing import get_origin, Self
from laza.common.proxy import proxy

from laza.common.functools import ( 
    export, cached_property
)

from laza.common.functools import calling_frame

from libs.di.laza.di.exc import DuplicateProviderError



from .common import (
    InjectionMarker,
    Injectable, 
    T_Injectable,
    T_Injected,
)

from . import providers as p
from .containers import InjectorContainer, IocContainer
from .context import InjectorContext, context_manager
from .functools import Bootable

logger = logging.getLogger(__name__)

_D = t.TypeVar("_D")


TContextBinding =  Callable[['InjectorContext', t.Optional[Injectable]], Callable[..., T_Injected]]





class BindingsDict(dict[Injectable, TContextBinding]):

    __slots__ = 'injector',

    injector: 'Injector'

    def __init__(self, injector: 'Injector'):
        self.injector = injector

    def __missing__(self, key):
        inj = self.injector
        provider = inj.get_provider(key)
        if not provider is None:
            return self.setdefault(key, provider.bind(inj, key))
        




@export
class Injector(Bootable, p.RegistrarMixin):
    """"""

    # _lock: Lock = None
    # bootid: int = None
    # booted: bool = None
    # _onboot_callbacks: list[t.Union['Bootable', Callable]] = None


    name: str
    parent: 'Injector'
    children: orderedset['Injector']
    
    _bindings: 'BindingsDict'
    _live_contexts: dict['InjectorContext', t.Union[Token, None]]

    _injector_context_class: type[InjectorContext] = InjectorContext

    container: InjectorContainer
    containers: orderedset[IocContainer]
    _container_class: type[InjectorContainer] = InjectorContainer

    def __init__(self, parent: 'Injector'=None, *, name: str=None):
        super().__init__()

        if  name is None:
            cf = calling_frame()
            self.name = cf.get('__name__') or cf.get('__package__') or '<anonymous>'
        else:
            self.name = name

        self.parent = None

        
        self._live_contexts = dict()
        self.children = orderedset()
        # self._checkouts = 0
        # self.current_context = None 

        self.container = self._container_class(self)

        self._bindings = BindingsDict(self)

        if not parent is None:
            self.set_parent(parent)


    @cached_property
    def _registry(self) -> MultiChainMap[T_Injectable, p.Provider]:
        return self._create_registry()

    @cached_property
    def _linked_deps(self) -> dict[SafeReferenceType[T_Injectable], SafeRefSet[T_Injectable]]:
        return SafeKeyRefDict.using(lambda: fallback_default_dict(SafeRefSet))()

    def _boot(self):
        self._setup_default_providers()
        self._setup_containers()

    def set_parent(self, parent: 'Injector'):
        if not self.parent is None:
            if self.parent is parent:
                return self
            raise TypeError(f'{self} already has parent: {self.parent}.')

        self.parent = parent
        parent.add_child(self)

        return self    
    
    def add_child(self, child: 'Injector'):
        if child in self.children:
            raise TypeError(f'{self} already has child: {child}.')

        self.children.add(child)
        return self

    def parents(self):
        parent = self.parent
        while not parent is None:
            yield parent
            parent = parent.parent

    def register_provider(self, provider: p.Provider) -> Self:
        self.container.register_provider(provider)
        return self

    def require(self, *containers) -> Self:
        self.container.require(*containers)
        return self

    def is_provided(self, obj: Injectable, *, only_self=False, strict=True) -> bool:
        if not (isinstance(obj, p.Provider) or obj in self._bindings):
            provider = self.get_provider(obj, strict=strict)
            if provider is None:
                if not only_self and self.parent:
                    return self.parent.is_provided(obj, strict=strict)
                return False
        return True

    def _get_provider(self, obj: Injectable, default=None, *, all=False, strict=True):
        rv = self._registry.get(obj)
        if rv is None:
            if isinstance(obj, p.Provider):
                rv = obj
            elif isinstance(obj, InjectionMarker):
                rv = self._registry.get(obj.__dependency__)
            else:
                origin = get_origin(obj)
                if origin is None:
                    return default
                rv = self._registry.get(origin)
            if rv is None:
                return default
        
        if strict is False or rv.can_bind(self, obj):
            return rv

        return default

    def get_provider(self, obj: Injectable, default=None, *, strict=True):
        
        key = obj
        if isinstance(obj, InjectionMarker):
            key = obj.__dependency__

        if isinstance(key, p.Provider):
            if strict is False or key.can_bind(self, obj):
                return key
            return default
       
        plist = self._registry.get_all(obj)
        if plist is None:
            origin = get_origin(obj)
            if origin is None:
                return default

            plist = self._registry.get_all(origin)
            if plist is None:
                return default

        stack = [v for v in reversed(plist) if strict is False or v.can_bind(self, obj)]
        stack = [v for v in stack if not v.is_default] or stack

        if stack:
            top, *extra = stack
            if extra:
                top = top.substitute(*extra)
            return top            

        return default

    def iter_providers(self, obj: Injectable, default=None, *, strict=True):
        key = obj
        plist = self._registry.get_all(key)
        if not plist:
            if isinstance(obj, InjectionMarker):
                key = self._registry.get(obj.__dependency__)
            
            logger.debug(f'{self}.iter_providers({obj}): {self._registry.count(key)}')

            if pp := next(it, None):
                for p in it:
                    yield p

        # if rv is None:
        #     if isinstance(obj, p.Provider):
        #         rv = obj
        #     elif isinstance(obj, DependencyMarker):
        #         rv = self._registry.get(obj.__injection_marker__)
        #     else:
        #         origin = get_origin(obj)
        #         if origin is None:
        #             return default
        #         rv = self._registry.get(origin)
        #     if rv is None:
        #         return default
        
        # if strict is False or rv.can_bind(self, obj):
        #     return rv

        # return default

    def make(self, parent: InjectorContext=None) -> InjectorContext:
        prt = self.parent
        if (parent and parent.injector) != prt:
            if prt and (not parent or parent.injector in prt):
                parent = prt.make(parent)
            else:
                raise ValueError(
                    f'Error creating Injector. Invalid parent injector {parent=} '
                    f'from {parent.injector=}. Expected {prt!r}.'
                )

        self.boot()
        rv = self._injector_context_class(self, parent)
        return rv

    def _push(self, ctx: InjectorContext, head: InjectorContext=None):
        if ctx in self._live_contexts:
            raise RuntimeError(f'{ctx} already pushed.')

        if head is None:
            self._live_contexts[ctx] = context_manager.set(ctx)
        else:
            self._live_contexts[ctx] = None

    def _pop(self, ctx: InjectorContext):
        token = self._live_contexts.pop(ctx)
        if token is not None:
            context_manager.reset(token)

    def flush(self, key: Injectable, source=None, *, skip_: orderedset=None):
        # sk = self, key

        # if skip_ is None: 
        #     skip_ = orderedset()
        # elif sk in skip_:
        #     return

        # skip_.add(sk)
        
        # for scope in self._live_contexts:
        #     del scope.vars[key]
        
        # if linked := self._linked_deps.pop(key, None):
        #     for dep in linked:
        #         self.flush(dep, skip_=skip_)

        # self._bindings.pop(key, None)
                    
        for d in self.children: 
            d.flush(key, source or self, _skip=skip_)

    def _create_registry(self):
        return MultiChainMap(*(d._registry for d in reversed(self.containers)))
    
    def _setup_containers(self):
        self.containers = orderedset(self.container.bind())

    def _setup_default_providers(self):
        self.register_provider(p.UnionProvider())
        self.register_provider(p.AnnotatedProvider())
        self.register_provider(p.InjectProvider())
   
    # def __contains__(self, x):
    #     if self.booted is True:
    #         if isinstance(x, IocContainer):
    #             return x in self.containers \
    #                 or x.is_singleton and x in (self.parent or ())
    #         elif isinstance(x, Injector):
    #             return x is self
    #         # else:
    #         #     return x in self._registry\
    #         #         or x in (self.parent or ())
    #     elif isinstance(x, IocContainer):
    #         return x in self._requires \
    #             or any(x in d for d in self._requires) \
    #             or x.is_singleton and x in (self.parent or ())
    #     else:
    #         return x == self
       
    def __str__(self) -> str:
        parent = self.parent
        return f'{self.__class__.__name__}({self.name!r}, {parent=!s})'

    def __repr__(self) -> str:
        parent = self.parent
        containers = [*getattr(self, 'containers', ())]
        return f'{self.__class__.__name__}({self.name!r}, {containers=!r}, {parent=!r})'

   