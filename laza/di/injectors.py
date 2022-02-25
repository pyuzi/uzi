from functools import update_wrapper
import sys
import typing as t 
import logging
from weakref import finalize, ref
from collections.abc import Callable


from laza.common.collections import MultiChainMap, frozenorderedset, orderedset, frozendict
from laza.common.typing import get_origin, Self

from laza.common.functools import ( 
    export
)

from laza.common.functools import calling_frame, uniqueid

from laza.common.promises import Promise





from .common import (
    InjectionMarker,
    Injectable, 
    T_Injectable,
    T_Injected,
    isinjectable,
)

from .containers import InjectorContainer, Container
from .context import InjectorContext, context_partial, wire
from .providers import (
    Alias, Provider, UnionProvider, AnnotatedProvider, 
    InjectProvider, PartialFactory
)
from .providers.tools import BindingsMap, ProviderResolver, ProviderRegistry

logger = logging.getLogger(__name__)

_T_Fn = t.TypeVar('_T_Fn', bound=Callable)




def inject(func: _T_Fn, /, *, provider: 'Provider'=None) -> _T_Fn:
    if provider is None:
        provider = PartialFactory(func)
    
    return update_wrapper(context_partial(provider), func)
    






@export
class Injector(ProviderRegistry):
    """"""

    __slots__ = (
        '__name', '__parent', '__bindings', '__container', 
        '__containers', '__boot', '__registry', '__resolver',
        '__bootstrapped', '__autoloads',
    )

    __boot: Promise

    __name: str
    __parent: Self
    
    __bindings: BindingsMap
    __resolver: ProviderResolver
    __registry: MultiChainMap[Injectable, Provider]

    __container: InjectorContainer
    __containers: orderedset[Container]

    _context_class: type[InjectorContext] = InjectorContext
    _container_class: type[InjectorContainer] = InjectorContainer
    _resolver_class: type[ProviderResolver] = ProviderResolver

    def __init__(self, parent: 'Injector'=None, *, name: str=None):
        if  name is None:
            cf = calling_frame()
            self.__name = cf.get('__name__') or cf.get('__package__') or '<anonymous>'
        else:
            self.__name = name

        self.__parent = parent
        self.__bootstrapped = False
        self.__boot = Promise().then(lambda: self.__bootstrap())

        self.__container = self._container_class(self)
        self.__registry = MultiChainMap()
        self.__resolver = self._resolver_class(self, self.__registry)
        self.__bindings = BindingsMap(self, self.__resolver)

    @property
    def name(self):
        return self.__name

    @property
    def parent(self):
        return self.__parent

    @property
    def bindings(self):
        return self.__bindings

    @property
    def container(self):
        return self.__container

    @property
    def containers(self):
        return self.__containers

    def onboot(self, callback: t.Union[Promise, Callable, None]=None):
        self.__boot.then(callback)

    def bootstrap(self) -> Self:
        self.__boot.settle()
        return self

    def set_parent(self, parent: 'Injector'):
        if not self.__parent is None:
            if self.__parent is parent:
                return self
            raise TypeError(f'{self} already has parent: {self.__parent}.')
        elif self.__boot.done():
            raise TypeError(f'{self} already bootstrapped.')

        self.__parent = parent
        return self    

    def parents(self):
        parent = self.__parent
        while not parent is None:
            yield parent
            parent = parent.parent

    def register(self, provider: Provider) -> Self:
        self.__container.register(provider)
        return self

    def require(self, *containers) -> Self:
        self.__container.include(*containers)
        return self

    def has_scope(self, scope: t.Union['Injector', Container, None]):
        return self.is_scope(scope) or self.__parent.has_scope(scope)

    def is_scope(self, scope: t.Union['Injector', Container, None]):
        return scope is None or scope is self or scope in self.__containers

    def is_provided(self, obj: Injectable, *, onlyself=False) -> bool:
        if not (isinstance(obj, InjectionMarker) or obj in self.__bindings):
            if isinjectable(obj):
                provider =  self.__resolver.resolve(obj)
                if provider is None:
                    if not onlyself and self.__parent:
                        return self.__parent.is_provided(obj)
                    return False
            else:
                return False
        return True

    def create_context(self, top: InjectorContext) -> InjectorContext:
        if parent := self.__parent:
            if not top.injector is parent:
                top = parent.create_context(top)

        self.__boot.settle()
        ctx = self._context_class(self, top)
        if auto := self.__autoloads:
            for d in auto:
                if fn := ctx[d]:
                    fn()
        return ctx

    def __bootstrap(self):
        if self.__bootstrapped is False:
            self.__bootstrapped = True
            logger.debug(f'BOOTSTRAP: {self}')
            comp = dict(self.__container.bind())
            self.__containers = frozenorderedset(comp.keys())
            self.__registry.maps = [frozendict(), *reversed(comp.values())]
            self._register_default_providers()
            self.onboot(lambda: self._collect_autoloaded())

    def _register_default_providers(self):
        self.register(UnionProvider().final())
        self.register(AnnotatedProvider().final())
        self.register(InjectProvider().final())
        for container in self.containers:
            self.register(Alias(container, self).final())

    def _collect_autoloaded(self):
        self.__autoloads = frozenset(
            a for c in self.__containers 
                for a in c.autoloads 
                    if (p := self.__resolver.resolve(a)) and p.autoloaded
        )

    def __repr__(self) -> str:
        parent = self.__parent
        return f'{self.__class__.__name__}({self.__name!r}, {parent=!s})'

  