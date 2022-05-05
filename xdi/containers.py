from contextvars import ContextVar
from email.policy import default
import operator
from threading import Lock
import typing as t
from logging import getLogger
from collections import abc
from typing_extensions import Self

import attr

from .core import is_injectable
from .exceptions import FinalProviderOverrideError, ProError


from . import Injectable, signals
from ._bindings import _T_Binding, LookupErrorBinding
from .markers import GUARDED, PRIVATE, PROTECTED, PUBLIC, AccessLevel, DepKey, _PredicateOpsMixin, DepSrc, ProNoopPredicate, ProPredicate
from ._common import ReadonlyDict, private_setattr, FrozenDict
from .providers import Provider, AbstractProviderRegistry


if t.TYPE_CHECKING: # pragma: no cover
    from .scopes import Scope


logger = getLogger(__name__)

_T_Pro = tuple['Container']
_T_BindKey = t.Union[DepKey, Injectable]




@ProPredicate.register
@private_setattr(frozen='_frozen')
class Container(_PredicateOpsMixin, AbstractProviderRegistry, ReadonlyDict[Injectable, Provider]):
    """A mapping of dependencies to their providers. We use them to bind 
    dependencies to their providers. 
   
    Attributes:
        name (str): The container's name
        bases (tuple[Container]): The container's bases
        default_access_level (AccessLevel): The default `access_level` to assign 
        to providers registered in this container
    """
    __slots__ = 'name', 'bases', 'default_access_level', '_pro',

    name: str
    bases: tuple[Self]
    default_access_level: AccessLevel 
    _pro: FrozenDict[Self, int]
    
    __setitem = dict[Injectable,  Provider].__setitem__
    __contains = dict[Injectable,  Provider].__contains__

    def __init__(self, name: str='<anonymous>', *bases: Self, access_level: AccessLevel=PUBLIC) -> None:
        """Create a container.
        
        Params:
            name (str, optional): Name of the container
            *bases (Container, optional): Base container.
            access_level (AccessLevel, optional): The default `access_level`
                to assign providers
        """
        self.__setattr(_pro=None, bases=(), name=name, default_access_level=AccessLevel(access_level))
        bases and self.extend(*bases)
        signals.on_container_create.send(self.__class__, container=self)

    @property
    def _frozen(self) -> bool:
        return not not self._pro

    @property
    def pro(self):
        """The container's provider resolution order.
        
        Like python's class `__mro__` the `pro` is computed using 
        [C3 linearization](https://en.wikipedia.org/wiki/C3_linearization)

        Returns:
            pro (FrozenDict[Container, int]): 
        """
        if pro := self._pro:
            return pro
        self.__setattr(_pro=self._evaluate_pro())
        return self._pro

    def pro_entries(self, it: abc.Iterable['Container'], bindings: 'BindingResolver', src: DepSrc) -> abc.Iterable['Container']:
        pro = self.pro
        return tuple(c for c in it if c in pro)
        
    def _evaluate_pro(self):
        bases = [*self.bases]

        if not bases:
            return FrozenDict({ self : 0 })

        ml = [*([*b.pro] for b in bases), [*bases]]
        res = {self: 0}
        
        i, miss = 0, 0
        while ml:
            if i == len(ml):
                if miss >= i:
                    raise ProError(f'Cannot create a consistent provider resolution order {miss=}, {ml=}')
                i = 0
            ls = ml[i]
            h = ls[0]
            if h in res:
                pass
            elif any(l.index(h) > 0 for l in  ml if not l is ls and h in l):
                i += 1
                miss += 1
                continue
            else:
                res[h] = i
            ls.pop(0)
            miss = 0
            if ls:
                i += 1
            else:
                ml.pop(i)

        return FrozenDict({c: i for i,c in enumerate(res)})

    def extend(self, *bases: Self) -> Self:
        """Adds containers to extended by this container.
        Args:
            *bases (Container): The base containers to be extended
            
        Returns:
            Self: this container
        """
        self.__setattr(bases=tuple(dict.fromkeys(self.bases + bases)))
        return self

    def extends(self, other: Self) -> bool:
        """Check whether this container extends the given base. 
        
        Params:
            base (Container): The base container to check

        Returns:
            bool:
        """
        return other in self.pro

    def access_level(self, accessor: Self):
        """Get the `AccessLevel` 

        Params:
            accessor (Container): 

        Returns:
            access_level (AccessLevel):
        """
        if accessor is self:
            return PRIVATE
        elif self.extends(accessor):
            return GUARDED
        elif accessor.extends(self):
            return PROTECTED
        else:
            return PUBLIC

    def new_binding_resolver(self, *, cls: type['BindingResolver']=None):
        return (cls or BindingResolver)(self)

    def _on_register(self, abstract: Injectable, provider: Provider):
        pass

    def __contains__(self, x):
        return self.__contains(x) or any(x in b for b in self.bases)

    def __setitem__(self, key: Injectable, provider: Provider) -> Self:
        """Register a dependency provider 
        
            container[_T] = providers.Value('abc')

        Params:
            abstract (Injectable): The dependency to be provided
            provider (Provider): The provider to provide the dependency
        """
        if not is_injectable(key):
            raise TypeError(f'expected `Injectable` not. `{key.__class__.__qualname__}`')

        if prov := provider._setup(self, key):
            self._on_register(key, prov)
            self.__setitem(key, prov)
            signals.on_provider_registered.send(self, abstract=key, provider=provider)

    def __missing__(self, key):
        if isinstance(key, Provider) and (key.container or self) is self:
            return key
            
    def _resolve(self, key: DepKey, bindings: 'BindingResolver'):
        if prov := self[key.abstract]:
            access = prov.access_level or self.default_access_level
            if access in self.access_level(key.container):
                if prov._can_resolve(key, bindings):
                    return prov,
        return ()

    def __bool__(self):
        return True
    
    def __eq__(self, o) -> bool:
        return o is self or (False if isinstance(o, Container) else NotImplemented)

    def __ne__(self, o) -> bool:
        return not o is self or (True if isinstance(o, Container) else NotImplemented)

    def __hash__(self):
        return hash(id(self))

    def __repr__(self):
        return f'{self.__class__.__name__}({self.name!r})'





@private_setattr
class ProMap(ReadonlyDict[DepSrc, _T_Pro]):
    __slots__ = 'bindings', 'pro',

    bindings: 'BindingResolver'
    pro: FrozenDict[Container, int]

    __contains = dict.__contains__
    __setdefault = dict.setdefault

    def __init__(self, bindings: 'BindingResolver'):
        base = bindings.parent.pros
        pro = {c:i for i,c in enumerate(bindings.container.pro) if not c in base}
        if not pro:
            raise ProError(f'{bindings.name}')
        self.__setattr(bindings=bindings, pro=FrozenDict(pro))

    def __contains__(self, x) -> bool:
        return x in self.pro or self.__contains(x)
    
    def __missing__(self, src: DepSrc):
        pro, bindings = tuple(self.pro), self.bindings
        src.bindings.extends(bindings)
        pro = src.predicate.pro_entries(pro, bindings, src)
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



@private_setattr(frozen='_frozen')
class BindingResolver(ReadonlyDict[_T_BindKey, _T_Binding]):
    """An isolated dependency resolution `bindings` for a given container. 

    Bindingss assemble the dependency graphs of dependencies registered in their container.

    Attributes:
        container (Container): The container who's bindings we are creating
        parent (Bindings): The parent bindings. Defaults to None

    Args:
        container (Container): The container who's bindings we are creating
        parent (Bindings, optional): The parent bindings. Defaults to NullBindings

    """
    __slots__ = 'container', 'parent', 'pros', 'stack', 'scope', 'keyclass'
    
    container: 'Container'
    parent: Self
    pros: ProMap
    stack: ResolutionStack
    scope: 'Scope'
    keyclass: type[DepKey]

    __contains = dict.__contains__
    __setdefault = dict.setdefault

    def __init__(self, container: Container):
        self.__setattr(container=container)
    
    @property
    def _frozen(self) -> int:
        return hasattr(self, 'scope')

    @property
    def level(self) -> int:
        return self.parent.level + 1

    def parents(self):
        """Returns a generetor that iterates over the bindings's ancestor starting 
        from the current `parent` to the root bindings.

        Yields:
            ancestor (Bindings): an ancestor.
        """
        parent = self.parent
        while parent:
            yield parent
            parent = parent.parent

    def __bool__(self):
        return True
    
    def __contains__(self, o) -> bool:
        return self.__contains(o) or o in self.pros or o in self.parent

    def setup(self, scope: 'Scope'):
        if hasattr(self, 'scope'):
            raise AttributeError(f'`scope already set.`')
        
        parent = scope.parent
        self.__setattr(
            scope=scope,
            pros=ProMap(self),
            parent=parent and parent.bindings or NullBindings(),
            stack=ResolutionStack(self.container),
            keyclass=type(f'BindingsKey', (DepKey,), {'scope': scope})
        )

    def extends(self, bindings: Self):
        return bindings is self or self.parent.extends(bindings)

    def make_key(self, abstract: Injectable, container: 'Container'=None, predicate: ProPredicate=ProNoopPredicate()):
        if isinstance(abstract, DepKey):
            return abstract
        else:
            return self.keyclass(
                abstract,
                container or (self.stack.top.container),
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
    
    def resolve_binding(self, dep_: _T_BindKey, *, recursive: bool=True):
        if not (bind := self.get(dep_, Missing)) is Missing:
            if recursive or not bind or self is bind.bindings:
                return bind
        elif dep_ != (dep := self.make_key(dep_)):
            bind = self.resolve_binding(dep)
            if dep in self:
                bind = self.__setdefault(dep_, bind)
            if recursive or not bind or self is bind.bindings:
                return bind
        elif is_injectable(dep.abstract):
            abstract = dep.abstract

            if prov := self.find_provider(dep):

                if prov.container and not prov.container is dep.container:
                    return self.__setdefault(dep, self[self.make_key(abstract, prov.container)])
                
                with self.stack.push(prov, abstract):
                    if bind := prov._resolve(abstract, self):
                        return self.__setdefault(dep, bind)
            elif origin := t.get_origin(abstract):
                if is_dependency_marker(origin):
                    if prov := self.find_provider(dep.replace(abstract=t.get_origin(abstract))):
                        with self.stack.push(prov, abstract):
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
        if isinstance(o, BindingResolver):
            return o is self
        return NotImplemented

    def __ne__(self, o) -> bool:
        if isinstance(o, BindingResolver):
            return not o is self
        return NotImplemented

    def __hash__(self):
        return id(self)





class NullBindings(BindingResolver):
    """A 'noop' `Bindings` used as the parent of root scopes.  

    Attributes:
        container (frozendict): 
        parent (None): The parent bindings

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
    def extends(self, bindings: Self):
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
            raise TypeError(f'Bindings keys must be `Injectable` not `{key.__class__.__qualname__}`')
        

