from abc import abstractmethod
from contextvars import ContextVar, Token
from functools import update_wrapper
import sys
import typing as t 
import logging
from weakref import finalize, ref
from collections.abc import Mapping, Callable, Sequence, Generator
from build import Mapping


from laza.common.collections import MultiChainMap, fallback_default_dict, nonedict, orderedset, fallbackdict
from laza.common.typing import get_origin, Self
from laza.common.proxy import proxy

from laza.common.functools import ( 
    export
)

from laza.common.functools import calling_frame, uniqueid
from laza.common.abc import abstractclass

from laza.common.promises import Promise




from .common import (
    InjectionMarker,
    Injectable, 
    T_Injectable,
    T_Injected,
)

from .containers import InjectorContainer, Container
from .context import InjectorContext, context_partial, _current_context
from .providers import (
    Provider, UnionProvider, AnnotatedProvider, 
    InjectProvider, RegistrarMixin, PartialFactory
)

logger = logging.getLogger(__name__)

_T_Fn = t.TypeVar('_T_Fn', bound=Callable)


TContextBinding =  Callable[['InjectorContext', t.Optional[Injectable]], Callable[..., T_Injected]]


def inject(func: _T_Fn, /, *, provider: 'Provider'=None) -> _T_Fn:
    if provider is None:
        provider = PartialFactory(func)
    
    return update_wrapper(context_partial(provider), func)
    






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
@abstractclass
class BaseInjector(RegistrarMixin):
    """"""

    __slots__ = (
        'name', 'parent', 'children', '_bindings', 'container', 
        'containers', '_onboot', '_registry'
    )

    _onboot: Promise

    name: str
    parent: 'BaseInjector'
    children: orderedset['BaseInjector']
    
    _bindings: 'BindingsDict'
    _providers: dict[Injectable, Provider]

    _InjectorContext: type[InjectorContext] = InjectorContext

    container: InjectorContainer
    containers: orderedset[Container]
    _InjectorContainer: type[InjectorContainer] = InjectorContainer


    def __init__(self, parent: 'Injector'=None, *, name: str=None):

        if  name is None:
            cf = calling_frame()
            self.name = cf.get('__name__') or cf.get('__package__') or '<anonymous>'
        else:
            self.name = name

        self.parent = None
        self._onboot = Promise()
        self.children = orderedset()
        self.container = self._InjectorContainer(self)
        self._bindings = BindingsDict(self)
        parent is None or self.set_parent(parent)

    def boot(self) -> Self:
        if self._onboot.is_pending:
            logger.debug(f'BOOTING:{self} => {self._onboot}')
            self._do_boot() 
            logger.debug(f'BOOTED:{self}  => {self._onboot}')
        return self

    def _do_boot(self):
        logger.debug(f'{self.__class__.__name__}._booted(START) --> {self}')
        self._setup_containers()
        self._setup_default_providers()
        
        self._onboot.fulfil(uniqueid[Container])
        
        self._boot_containers()
        self._setup_registry()

        logger.debug(f'{self.__class__.__name__}._booted({" <=|=> ".join(map(repr, [*self.containers]))})')

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

    def register_provider(self, provider: Provider) -> Self:
        self.container.register_provider(provider)
        return self

    def require(self, *containers) -> Self:
        self.container.require(*containers)
        return self

    def has_scope(self, scope: t.Union['Injector', Container, None]):
        return self.is_scope(scope) or self.parent.has_scope(scope)

    def is_scope(self, scope: t.Union['Injector', Container, None]):
        return scope is None or scope is self or scope in self.containers

    def is_provided(self, obj: Injectable, *, onlyself=False, check=True) -> bool:
        if not (isinstance(obj, Provider) or obj in self._bindings):
            provider = self.get_provider(obj, check=check)
            if provider is None:
                if not onlyself and self.parent:
                    return self.parent.is_provided(obj, check=check)
                return False
        return True

    def get_provider(self, obj: Injectable, default=None, *, check=True):
        key = obj
        if isinstance(obj, InjectionMarker):
            key = obj.__dependency__

        if isinstance(key, Provider):
            if check is False or key.can_bind(self, obj):
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

        return self._reduce_providers(obj, plist, default, check=check)

    def _reduce_providers(self, obj: Injectable, plist: Sequence[Provider], default=None, *, check=True):
        stack = [v for v in reversed(plist) if check is False or v.can_bind(self, obj)]
        stack = [v for v in stack if not v.is_default] or stack

        if stack:
            top, *extra = stack
            if extra:
                top = top.substitute(*extra)
            return top            

        return default

    def create_context(self, top: InjectorContext=None) -> InjectorContext:
        if top is None:
            top = _current_context()

        if parent := self.parent:
            if not top.injector is parent:
                top = parent.create_context(top)
        self.boot()
        return self._InjectorContext(self, top)

    make = create_context

    def _setup_registry(self, *v):
        self._registry = MultiChainMap(*(d._registry for d in reversed(self.containers)))
    
    def _setup_containers(self, *v):
        logger.debug(f'{self.__class__.__name__}._setup_containers(START) --> {self}')
        self.containers = orderedset(self.container.bind())

    def _boot_containers(self, *v):
        for c in self.containers:
            c.boot()

    def _setup_default_providers(self):
        self.register_provider(UnionProvider().final())
        self.register_provider(AnnotatedProvider().final())
        self.register_provider(InjectProvider().final())
   
    # def __contains__(self, x):
    #     if self.booted is True:
    #         if isinstance(x, Container):
    #             return x in self.containers \
    #                 or x.is_singleton and x in (self.parent or ())
    #         elif isinstance(x, Injector):
    #             return x is self
    #         # else:
    #         #     return x in self._registry\
    #         #         or x in (self.parent or ())
    #     elif isinstance(x, Container):
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



@export
class Injector(BaseInjector):
    
    __slots__ = ()



@export
class NoopInjector(BaseInjector):
    
    __slots__ = ()

    # def has