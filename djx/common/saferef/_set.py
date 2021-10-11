# Access WeakSet through the weakref module.
# This code is separated-out because it is needed
# by abc.py to load everything else at startup.
import typing as t

from types import GenericAlias

from collections.abc import MutableSet


from . import saferef as ref, ReferenceType, weakref


__all__ = ['SafeRefSet']

_T = t.TypeVar('_T', bound=t.Hashable)


class _IterationGuard:
    # This context manager registers itself in the current iterators of the
    # weak container, such as to delay all removals until the context manager
    # exits.
    # This technique should be relatively thread-safe (since sets are).
    
    __slots__ = 'weakcontainer', '__weakref__',


    def __init__(self, weakcontainer):
        # Don't create cycles
        self.weakcontainer = weakref(weakcontainer)

    def __enter__(self):
        w = self.weakcontainer()
        if w is not None:
            w._iterating.add(self)
        return self

    def __exit__(self, e, t, b):
        w = self.weakcontainer()
        if w is not None:
            s = w._iterating
            s.remove(self)
            if not s:
                w._commit_removals()






class SafeRefSet(t.Generic[_T]):

    __slots__ = 'data', '_factory', '_remove', '_pending_removals', '_iterating', '__weakref__'

    __factory__ = set

    data: set[ReferenceType[_T]]

    def __init__(self, data=None, factory=None):

        if factory is None:
            self.data = (self.__factory__ or set)()
        else:
            self.data = factory()
            assert isinstance(self.data, MutableSet)
        
        self._factory = factory


        def _remove(item, selfref=weakref(self)):
            self = selfref()
            if self is not None:
                if self._iterating:
                    self._pending_removals.append(item)
                else:
                    self.data.discard(item)

        self._remove = _remove
        # A list of keys to be removed
        self._pending_removals = []
        self._iterating = set()

        data is None or self.update(data)

    def _commit_removals(self):
        l = self._pending_removals
        discard = self.data.discard
        while l:
            discard(l.pop())

    def __iter__(self):
        with _IterationGuard(self):
            for itemref in self.data:
                item = itemref()
                if item is not None:
                    # Caveat: the iterator will keep a strong reference to
                    # `item` until it is resumed or closed.
                    yield item

    def __len__(self):
        return len(self.data) - len(self._pending_removals)

    def __contains__(self, item):
        try:
            wr = ref(item)
        except TypeError:
            return False
        return self.data.__contains__(wr)

    def __reduce__(self):
        return self.__class__, (list(self), self._factory)

    def add(self, item):
        if self._pending_removals:
            self._commit_removals()
        self.data.add(ref(item, self._remove))

    def clear(self):
        if self._pending_removals:
            self._commit_removals()
        self.data.clear()

    def copy(self):
        return self.__class__(self, factory=self._factory)

    def pop(self):
        if self._pending_removals:
            self._commit_removals()
        while True:
            try:
                itemref = self.data.pop()
            except KeyError:
                raise KeyError('pop from empty WeakSet') from None
            item = itemref()
            if item is not None:
                return item

    def remove(self, item):
        if self._pending_removals:
            self._commit_removals()
        self.data.remove(ref(item))

    def discard(self, item):
        if self._pending_removals:
            self._commit_removals()
        self.data.discard(ref(item))

    def update(self, other):
        if self._pending_removals:
            self._commit_removals()
        for element in other:
            self.add(element)

    def __ior__(self, other):
        self.update(other)
        return self

    def difference(self, other):
        newset = self.copy()
        newset.difference_update(other)
        return newset
    __sub__ = difference

    def difference_update(self, other):
        self.__isub__(other)

    def __isub__(self, other):
        if self._pending_removals:
            self._commit_removals()
        if self is other:
            self.data.clear()
        else:
            self.data.difference_update(ref(item) for item in other)
        return self

    def intersection(self, other):
        return self.__class__(item for item in other if item in self)
    __and__ = intersection

    def intersection_update(self, other):
        self.__iand__(other)
    def __iand__(self, other):
        if self._pending_removals:
            self._commit_removals()
        self.data.intersection_update(ref(item) for item in other)
        return self

    def issubset(self, other):
        return self.data.issubset(ref(item) for item in other)
    __le__ = issubset

    def __lt__(self, other):
        return self.data < set(map(ref, other))

    def issuperset(self, other):
        return self.data.issuperset(ref(item) for item in other)
    __ge__ = issuperset

    def __gt__(self, other):
        return self.data > set(map(ref, other))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.data == set(map(ref, other))

    def symmetric_difference(self, other):
        newset = self.copy()
        newset.symmetric_difference_update(other)
        return newset
    __xor__ = symmetric_difference

    def symmetric_difference_update(self, other):
        self.__ixor__(other)
    def __ixor__(self, other):
        if self._pending_removals:
            self._commit_removals()
        if self is other:
            self.data.clear()
        else:
            self.data.symmetric_difference_update(ref(item, self._remove) for item in other)
        return self

    def union(self, other):
        return self.__class__(e for s in (self, other) for e in s)
    __or__ = union

    def isdisjoint(self, other):
        return len(self.intersection(other)) == 0

    def __repr__(self):
        return repr(self.data)

    # __class_getitem__ = classmethod(GenericAlias)
