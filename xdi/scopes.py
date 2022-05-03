from contextlib import ExitStack, contextmanager, nullcontext
from contextvars import ContextVar
from functools import reduce
from itertools import chain
from logging import getLogger
from operator import or_
from re import S
import typing as t

import attr
from typing_extensions import Self
from collections import abc

from ._common import Missing, ReadonlyDict, private_setattr, FrozenDict
from .markers import AccessLevel, Dep, DepKey, DepSrc, ProNoopPredicate, ProPredicate, is_dependency_marker
from .providers import Provider

from .core import Injectable, is_injectable
from ._bindings import _T_Binding, LookupErrorBinding
from .exceptions import FinalProviderOverrideError, ProError
from .containers import Container

logger = getLogger(__name__)


_T_Pro = tuple[Container]
_T_Dep = t.Union[DepKey, Injectable]


@private_setattr
class _ProResolver(ReadonlyDict[DepSrc, _T_Pro]):
    __slots__ = 'scope', 'pro',

    scope: 'Scope'
    pro: FrozenDict[Container, int]

    __contains = dict.__contains__
    __setdefault = dict.setdefault

    def __init__(self, scope: 'Scope'):
        base = scope.parent.pros
        pro = {c:i for i,c in enumerate(scope.container.pro) if not c in base}
        if not pro:
            raise ProError(f'{scope.name}')
        self.__setattr(scope=scope, pro=FrozenDict(pro))

    def __contains__(self, x) -> bool:
        return x in self.pro or self.__contains(x)
    
    def __missing__(self, src: DepSrc):
        pro, scope = tuple(self.pro), self.scope
        src.scope.extends(scope)
        pro = src.predicate.pro_entries(pro, scope, src)
        return self.__setdefault(src, tuple(pro))
    

@private_setattr
class ResolutionStack(abc.Sequence):

    __slots__ = '__var',

    class StackItem(t.NamedTuple):
        container: Container
        abstract: Injectable = None
        provider: Provider = None

    __var: ContextVar[tuple[StackItem]]

    def __init__(self, default: Container):
        stack= self.StackItem(default),
        self.__var = ContextVar(f'{default.name}.{self.__class__.__name__}', default=stack)
        self.__var.set(stack)

    @property
    def top(self):
        return self[0]
     
    def push(self, provider: Provider, abstract: Injectable=None):
        top = self.top
        new = self.StackItem(
            provider.container or top.container, 
            abstract or provider.abstract or top.abstract,
            provider
        )
        self.__var.set((new,) + self[:])
        return self
        
    def pop(self):
        var = self.__var
        stack = var.get()
        if len(stack) < 2:
            raise ValueError(f'too many calls to pop()')
        var.set(stack[1:])
        return stack[0]
    
    def index(self, val, start=0, stop=None):
        stack = self.__var.get()[start:stop:]

        if isinstance(val, tuple):
            return stack.index(val)
        else:
            for i,x in enumerate(stack):
                if val in x:
                    return i
        raise ValueError(val)

    def __reversed__(self):
        yield from reversed(self.__var.get())

    def __contains__(self, k):
        stack = self.__var.get()
        if isinstance(k, tuple):
            return k in stack
        else:
            return any(k in x for x in stack)

    def __getitem__(self, k):
        return self.__var.get()[k]

    def __bool__(self):
        return True

    def __len__(self):
        return len(self.__var.get())

    def __iter__(self):
        return iter(self.__var.get())
    
    def __enter__(self):
        return self
    
    def __exit__(self, *e):
        self.pop()

    def __copy__(self, *a):
        raise TypeError(f'cannot copy {self.__class__.__qualname__}')
        
    __deepcopy__ = __reduce__ = __copy__ 



@attr.s(slots=True, frozen=True, cmp=False)
@private_setattr
class Scope(ReadonlyDict[_T_Dep, _T_Binding]):
    """An isolated dependency resolution `scope` for a given container. 

    Scopes assemble the dependency graphs of dependencies registered in their container.

    Attributes:
        container (Container): The container who's scope we are creating
        parent (Scope): The parent scope. Defaults to None

    Args:
        container (Container): The container who's scope we are creating
        parent (Scope, optional): The parent scope. Defaults to NullScope

    """
    container: 'Container' = attr.ib(repr=True)
    parent: Self = attr.ib(converter=lambda s=None: s or NullScope(), default=None)

    ident: tuple = attr.ib(init=False, repr=True)
    @ident.default
    def _init_ident(self):
        return  self.container, *self.parent.ident,

    _ash: int = attr.ib(init=False, repr=False)
    @_ash.default
    def _init_v_hash(self):
        return hash(self.ident)

    # # _injector_class: type[Injector] = attr.ib(kw_only=True, default=Injector, repr=False)
    
    _key_class: type[DepKey] = attr.ib(init=False, repr=False)
    @_key_class.default
    def _init__key_class(self):
        return type(f'ScopeDepKey', (DepKey,), {'scope': self})
        

    pros: _ProResolver = attr.ib(init=False, repr=False)
    @pros.default
    def _init_pros(self):
        return _ProResolver(self)

    _resolvestack: ResolutionStack = attr.ib(init=False, repr=False)
    @_resolvestack.default
    def _init_resolution_stack(self):
        return ResolutionStack(self.container)

    __contains = dict.__contains__
    __setdefault = dict.setdefault

    @property
    def name(self) -> str:
        """The name of the scope. Usually returns the scope's `container.name` 
        """
        return self.container.name

    @property
    def level(self) -> int:
        return self.parent.level + 1

    def parents(self):
        """Returns a generetor that iterates over the scope's ancestor starting 
        from the current `parent` to the root scope.

        Yields:
            ancestor (Scope): an ancestor.
        """
        parent = self.parent
        while parent:
            yield parent
            parent = parent.parent

    def __bool__(self):
        return True
    
    def __contains__(self, o) -> bool:
        return self.__contains(o) or o in self.pros or o in self.parent

    def extends(self, scope: Self):
        return scope is self or self.parent.extends(scope)

    def make_key(self, abstract: Injectable, container: 'Container'=None, predicate: ProPredicate=ProNoopPredicate()):
        if isinstance(abstract, DepKey):
            return abstract
        else:
            return self._key_class(
                abstract,
                container or (self._resolvestack.top.container),
                predicate
            )

    def find_provider(self, dep: DepKey):
        rv = [p for c in self.pros[dep.src] for p in c._resolve(dep, self)]
        if rv:
            if len(rv) > 1:
                rv.sort(key=lambda p: int(not not p.is_default))
                if final := next((p for p in rv if p.is_final), None):
                    if overrides := rv[:rv.index(final)]:
                        raise FinalProviderOverrideError(dep, final, overrides)
            return rv[0]
    
    def resolve_binding(self, dep_: _T_Dep, *, recursive: bool=True):
        if not (bind := self.get(dep_, Missing)) is Missing:
            if recursive or not bind or self is bind.scope:
                return bind
        elif dep_ != (dep := self.make_key(dep_)):
            bind = self.resolve_binding(dep)
            if dep in self:
                bind = self.__setdefault(dep_, bind)
            if recursive or not bind or self is bind.scope:
                return bind
        elif is_injectable(dep.abstract):
            abstract = dep.abstract

            if prov := self.find_provider(dep):

                if prov.container and not prov.container is dep.container:
                    return self.__setdefault(dep, self[self.make_key(abstract, prov.container)])
                
                with self._resolvestack.push(prov, abstract):
                    if bind := prov._resolve(abstract, self):
                        return self.__setdefault(dep, bind)
            elif origin := t.get_origin(abstract):
                if is_dependency_marker(origin):
                    if prov := self.find_provider(dep.replace(abstract=t.get_origin(abstract))):
                        with self._resolvestack.push(prov, abstract):
                            if bind := prov._resolve(abstract, self):
                                return self.__setdefault(dep, bind)
                elif bind := self.resolve_binding(dep.replace(abstract=origin), recursive=False):
                    return self.__setdefault(dep, bind)
                
            if recursive and ((bind := self.parent[dep]) or dep in self.parent):
                return self.__setdefault(dep, bind)
        else:
            raise TypeError(f'expected an `Injectable` not `{dep.abstract.__class__.__qualname__}`')

    __missing__ = resolve_binding

    def __eq__(self, o) -> bool:
        if isinstance(o, Scope):
            return o.ident == self.ident 
        return NotImplemented

    def __ne__(self, o) -> bool:
        if isinstance(o, Scope):
            return o.ident != self.ident 
        return NotImplemented

    def __hash__(self):
        return self._ash





class NullScope(Scope):
    """A 'noop' `Scope` used as the parent of root scopes.  

    Attributes:
        container (frozendict): 
        parent (None): The parent scope

    Params:
        None

    """

    __slots__ = ()
    parent = None
    container = FrozenDict()
    pros = FrozenDict()
    level = -1
    ident = ()
    _ash = hash(ident)
    
    name = '<null>'

    def __init__(self) -> None: ...
    def extends(self, scope: Self):
        return False
    def __bool__(self): 
        return False
    def __repr__(self): 
        return f'{self.__class__.__name__}()'
    def __contains__(self, key): 
        return False
    def __getitem__(self, key):
        if is_injectable(key):
            return LookupErrorBinding(key, self)
        elif isinstance(key, DepKey) and is_injectable(key.abstract):
            return LookupErrorBinding(key.abstract, self)
        else:
            raise TypeError(f'Scope keys must be `Injectable` not `{key.__class__.__qualname__}`')
        

