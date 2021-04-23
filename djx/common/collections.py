from itertools import chain
from typing import Generic, Optional, TYPE_CHECKING, TypeVar, overload
from collections.abc import (
    Hashable, Mapping, MutableSet, Iterable, Set, MutableSequence, 
    Callable, ItemsView, ValuesView
)


from .utils import export
from .abc import FluentMapping, Orderable

_empty = object()

_T_Ordered = TypeVar('_T_Ordered', bound=Hashable)
TK = TypeVar('TK')
TV = TypeVar('TV')
TM = TypeVar('TM', bound=Mapping)




def _noop(*k):
    return None




@export()
@FluentMapping.register
class fluentdict(dict[TK, TV]):
    """A dict that retruns a fallback value when a missing key is retrived.
    
    Unlike defaultdict, the fallback value will not be set.
    """
    __slots__ = ('fallback_factory',)

    fallback_factory: Optional[Callable[[TK], Optional[TV]]]

    def _set_fallback_factory(self, func=None):
        self.fallback_factory = _noop if func is None else func

    def __init__(self, fluentdict_fallback: Callable[[TK], Optional[TV]]=None, *args, **kwds):
        self._set_fallback_factory(fluentdict_fallback)
        super().__init__(*args, **kwds)

    def __missing__(self, key: TK) -> TV:
        return self.fallback_factory(key) 

    def copy(self):
        self.__class__(self.fallback_factory, self)

    __copy__ = copy





class _dictset(dict[_T_Ordered, _T_Ordered], Generic[_T_Ordered]):

    __slots__ = ()

    def __init__(self, *iterables: Iterable[_T_Ordered]):
        super().__init__((i, i) for it in iterables for i in it)
    
    def __or__(self, other):
        if not isinstance(other, Iterable):
            return NotImplemented
        return self._from_iterable(e for s in (self, other) for e in s)

    def __ror__(self, other):
        if not isinstance(other, Iterable):
            return NotImplemented
        return self._from_iterable(e for s in (other, self) for e in s)

    def __sub__(self, other):
        if not isinstance(other, (Set, Mapping)):
            if not isinstance(other, Iterable):
                return NotImplemented
            other = self._from_iterable(other)
        return self._from_iterable(value for value in self if value not in other)

    def __rsub__(self, other):
        if not isinstance(other, Iterable):
            return NotImplemented
        return self._from_iterable(value for value in other if value not in self)

    def __xor__(self, other):
        if not isinstance(other, Set):
            if not isinstance(other, Iterable):
                return NotImplemented
            other = self._from_iterable(other)
        return (self - other) | (other - self)

    def __rxor__(self, other):
        if not isinstance(other, Set):
            if not isinstance(other, Iterable):
                return NotImplemented
            other = self._from_iterable(other)
        return (other - self) | (self - other)

    
    
@export()
class FrozenOrderedset(_dictset[_T_Ordered], Set[_T_Ordered], Generic[_T_Ordered]):
    
    __slots__ = ()
    
    def _attr_error(name=''):
        def err(self):
            raise AttributeError(f'{name} on immutable {self.__class__}')
        err.__name__ = name or 'err'
        return err

    update = _attr_error('update')
    pop = _attr_error('pop')
    add = _attr_error('add')
    discard = _attr_error('discard')
    del _attr_error


@export()
class OrderedSet(_dictset[_T_Ordered], MutableSet[_T_Ordered], Generic[_T_Ordered]):
    
    __slots__ = ()

    def add(self, value):
        """Add an element."""
        self[value] = value

    def discard(self, value):
        """Remove an element.  Do not raise an exception if absent."""
        try:
            del self[value]
        except KeyError:
            pass

    def update(self, *iterables: Iterable[_T_Ordered]):
        """Add an element."""
        super().update((i, i) for it in iterables for i in it)
    
    def pop(self, val: _T_Ordered=_empty, *default):
        """Return the popped value.  Raise KeyError if empty."""
        if val is _empty:
            return self.popitem()[0]
        else:
            return self.pop(val, *default)
     





_T_Stack_K = TypeVar('_T_Stack_K')
_T_Stack_S = TypeVar('_T_Stack_S', bound=MutableSequence)
_T_Stack_V = TypeVar('_T_Stack_V', bound=Orderable)


class PriorityStack(dict[_T_Stack_K, _T_Stack_S], Generic[_T_Stack_K, _T_Stack_V, _T_Stack_S]):
    
    __slots__= ('stackfactory',)

    if TYPE_CHECKING:
        stackfactory: Callable[..., _T_Stack_S] = list[_T_Stack_V]

    def __init__(self, _stackfactory: Callable[..., _T_Stack_S]=list, /, *args, **kwds) -> None:
        self.stackfactory = _stackfactory or list
        super().__init__(*args, **kwds)

    @overload
    def remove(self, k: _T_Stack_K, val: _T_Stack_V):
        self[k:].remove(val)

    def setdefault(self, k: _T_Stack_V, val: _T_Stack_V) -> _T_Stack_V:
        stack = super().setdefault(k, self.stackfactory())
        stack or stack.append(val)
        return stack[-1]

    def copy(self):
        return type(self)(self.stackfactory, ((k, self[k:][:]) for k in self))
    
    __copy__ = copy

    get_all = dict[_T_Stack_K, _T_Stack_S].get
    def get(self, k: _T_Stack_K, default=None):
        try:
            return self[k]
        except (KeyError, IndexError):
            return default

    all_items = dict[_T_Stack_K, _T_Stack_S].items
    def items(self):
        return ItemsView[tuple[_T_Stack_K, _T_Stack_V]](self)

    def merge(self, __PriorityStack_arg=None, /, **kwds):
        
        if isinstance(__PriorityStack_arg, PriorityStack):
            items = chain(__PriorityStack_arg.all_items(), kwds.items())
        elif isinstance(__PriorityStack_arg, Mapping):
            items = chain(__PriorityStack_arg.items(), kwds.items())
        elif __PriorityStack_arg is not None:
            items = chain(__PriorityStack_arg, kwds.items())
        else:
            items = kwds.items()

        for k,v in items:
            stack = super().setdefault(k, self.stackfactory())
            stack.extend(v)
            stack.sort()

    replace = dict.update
    def update(self, __PriorityStack_arg=None, /, **kwds):
        if isinstance(__PriorityStack_arg, Mapping):
            items = chain(__PriorityStack_arg.items(), kwds.items())
        elif __PriorityStack_arg is not None:
            items = chain(__PriorityStack_arg, kwds.items())
        else:
            items = kwds.items()

        for k,v in items:
            self[k] = v

    all_values = dict[_T_Stack_K, _T_Stack_S].values
    def values(self):
        return ValuesView[_T_Stack_V](self)
        
    @overload
    def __getitem__(self, k: _T_Stack_K) -> _T_Stack_V: ...
    @overload
    def __getitem__(self, k: slice) -> _T_Stack_S: ...
    def __getitem__(self, k):
        if isinstance(k, slice):
            return super().__getitem__(k.start)
        else:
            return super().__getitem__(k)[-1]

    def __setitem__(self, k: _T_Stack_K, val: _T_Stack_V):
        stack = super().setdefault(k, self.stackfactory())
        stack.append(val)
        stack.sort()


