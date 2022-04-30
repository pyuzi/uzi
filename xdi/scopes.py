from contextvars import ContextVar
from functools import reduce
from itertools import chain
from logging import getLogger
from operator import or_
import typing as t

import attr
from typing_extensions import Self
from collections import abc

from ._common import Missing, private_setattr, FrozenDict
from .markers import AccessLevel, ProPredicate, is_dependency_marker
from .providers import Provider

from .core import Injectable, is_injectable
from ._bindings import _T_Binding, LookupErrorBinding
from .exceptions import FinalProviderOverrideError
from .containers import Container

logger = getLogger(__name__)


class EmptyScopeError(RuntimeError):
    ...


_T_Pro = tuple[Container]
_T_ProKey = tuple[Container, tuple[ProPredicate]]
_T_DepKey = tuple[Injectable, Container, ProPredicate]


# class _CanonicalProPaths(FrozenDict[_T_ProMapKey, _T_Binding]):
#     __slots__ = 'aliases',

#     aliases: FrozenDict[_T_ProMapKey, _T_ProKey]

#     __setdefault = dict.setdefault

#     def __init__(self, *pro: abc.Iterable[Container]):
#         static = pro[0]
#         canonized_root = static, (),
#         aliases = dict.fromkeys([
#             (), 
#             None,
#             (None,),
#             (None, ()),
#             (None, None),
#             *(k for c in pro for k in [c, (c,), (c, None), (c,())])
#         ], canonized_root)
#         aliases[canonized_root] = canonized_root
#         self.__setattr(aliases=FrozenDict(aliases))
#         assert all(k != v for k, v in self.aliases.values())

#     def __missing__(self, key: _T_Binding):
#         aliases, ke, i = self.aliases, key, 0
#         while ke in aliases:
#             i += 1
#             if ke == (ke := aliases[ke]):
#                 break
#         return self.__setdefault(key, ke) if i else ke


@private_setattr
class _ProMap(FrozenDict[_T_ProKey, _T_Pro]):
    __slots__ = 'scope', 'root',

    scope: 'Scope'
    # canonical: _CanonicalProPaths[_T_ProKey]
    root: tuple[Container]

    __setdefault = dict.setdefault

    def __init__(self, scope: 'Scope'):
        self.__setattr(scope=scope, root=tuple(scope.container.pro))

    def __missing__(self, key: _T_ProKey):
        dep, preds = key
        scope, pro = self.scope, self.root
        for pred in preds:
            pro = pred.pro_entries(pro, scope, dep)
        return self.__setdefault(key, tuple(pro))






@attr.s(slots=True, frozen=True, cmp=False)
@private_setattr
class Scope(FrozenDict[_T_DepKey, _T_Binding]):
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

    # _injector_class: type[Injector] = attr.ib(kw_only=True, default=Injector, repr=False)
    
    maps: abc.Set[Container] = attr.ib(init=False, repr=False)
    @maps.default
    def _init_maps(self):
        con = self.container
        dct = { c: i for i, c in enumerate(con.pro) }
        return t.cast(abc.Set[Container], dct.keys())

    pros: _ProMap = attr.ib(init=False, repr=False)
    @pros.default
    def _init_pros(self):
        return _ProMap(self)

    _resolve_stack: ContextVar[tuple[Provider]] = attr.ib(init=False, repr=False)
    @_resolve_stack.default
    def _init__resolve_stack(self):
        return _ProMap(self)

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
        return self.__contains(o) or o in self.maps or o in self.parent

    def access_level(self, container: Container, dependant: Container):
        if dependant is container:
            return AccessLevel.private
        elif container.extends(dependant):
            return AccessLevel.guarded
        elif dependant.extends(container):
            return AccessLevel.protected
        else:
            return AccessLevel.public
            
    def find_provider(self, abstract: Injectable, dependant: Container, *predicates: ProPredicate):
        pro = tuple(self.pros[dependant, predicates])
        rv = [p for c in pro if (p := c[abstract])]
        if rv:
            if len(rv) > 1:
                rv.sort(key=lambda p: int(not not p.is_default))
                if final := next((p for p in rv if p.is_final), None):
                    if overrides := rv[:rv.index(final)]:
                        raise FinalProviderOverrideError(abstract, final, overrides)
            return rv[0]
    
    def resolve_binding(self, key: _T_DepKey, *, recursive: bool=True):
        if self.__contains(key):
            res = self[key]
            if recursive or not res or self is res.scope:
                return res
            return
        elif not isinstance(key, tuple):
            tkey = key, self.container
            res = self.resolve_binding(tkey)
            if tkey in self:
                res = self.__setdefault(key, res)
            if recursive or not res or self is res.scope:
                return res
            return

        abstract, dependant, *predicates = key
        if is_injectable(abstract):
            if pro := self.find_provider(abstract, dependant, *predicates):
                if not pro.container in (None, dependant):
                    return self.__setdefault(key, self[abstract, pro.container])
                
                if bind := pro._resolve(abstract, self):
                    return self.__setdefault(key, bind)

            elif is_dependency_marker(abstract):
                if pro := self.find_provider(abstract.__origin__, dependant, *predicates):
                    if bind := pro._resolve(abstract, self):
                        return self.__setdefault(key, bind)
            elif origin := t.get_origin(abstract):
                if bind := self.resolve_binding((origin,) + key[1:], recursive=False):
                    return self.__setdefault(key, bind)
                
            if recursive and ((bind := self.parent[abstract]) or abstract in self.parent):
                return self.__setdefault(key, bind)
        else:
            raise TypeError(f'expected an `Injectable` not `{abstract.__class__.__qualname__}`')

    def __missing__(self, key: _T_DepKey):
        return self.resolve_binding(key)

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
    maps = frozenset()
    level = -1
    ident = ()
    _ash = hash(ident)
    
    name = '<null>'

    def __init__(self) -> None: ...

    def __bool__(self): 
        return False
    def __repr__(self): 
        return f'{self.__class__.__name__}()'
    def __contains__(self, key): 
        return False
    def __getitem__(self, key):
        if isinstance(key, tuple):
            abstract, *_ = key
        else:
            abstract = key

        if is_injectable(abstract):
            return LookupErrorBinding(abstract, self)
        else:
            raise TypeError(f'Scope keys must be `Injectable` not `{abstract.__class__.__qualname__}`')
        

