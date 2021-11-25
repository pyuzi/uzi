from abc import ABCMeta
from collections import ChainMap, UserString as _BaseUserStr
from inspect import signature
import sys
from copy import deepcopy
from functools import cache, wraps
from itertools import chain
from types import FunctionType, GeneratorType, GenericAlias, new_class
import typing as t
from collections.abc import (
    Hashable, Mapping, MutableMapping, MutableSet, Iterable, Set, Sequence, MutableSequence, 
    Callable, KeysView, ItemsView, ValuesView, Iterator, Sized, Reversible
)

from djx.common.saferef import saferef





from .utils import export, class_only_method, cached_class_property, assign
from .abc import FluentMapping, Orderable

_empty = object()

_T_Key = t.TypeVar('_T_Key', bound=Hashable)
_T_Val = t.TypeVar('_T_Val', covariant=True)
_T_Default = t.TypeVar('_T_Default', covariant=True)




def _noop_fn(k=None):
    return k



def _none_fn(k=None):
    return None




_FallbackCallable =  Callable[[_T_Key], t.Optional[_T_Val]]
_FallbackMap = Mapping[_T_Key, t.Optional[_T_Val]]
_FallbackType =  t.Union[_FallbackCallable[_T_Key, _T_Val], _FallbackMap[_T_Key, _T_Val], _T_Val, None] 

_TF = t.TypeVar('_TF', bound=_FallbackType[t.Any, t.Any])




@export()
class frozendict(dict[_T_Key, _T_Val]):

    __slots__ = '_hash', #'_frozen_',

    # if t.TYPE_CHECKING:
    #     _hash: int = 0

    _blank_instance_ = ...

    def __init_subclass__(cls, blank=...) -> None:
        cls._blank_instance_ = ... if blank is True \
            else None if not blank \
                else None if cls._blank_instance_ is None else ...

        return super().__init_subclass__()

    def __new__(cls, *args, **kwargs):
        if (args or kwargs) or cls._blank_instance_ is None:
            return super().__new__(cls)
        elif cls._blank_instance_ is ...:
            cls._blank_instance_ = super().__new__(cls)
        return cls._blank_instance_

    def __delitem__(self, k):
        raise TypeError(f'{self.__class__.__name__} is immutable')

    def __setitem__(self, k, v):
        raise TypeError(f'{self.__class__.__name__} is immutable')

    def setdefault(self, k, v):
        raise TypeError(f'{self.__class__.__name__} is immutable')

    def pop(self, k, *v):
        raise TypeError(f'{self.__class__.__name__} is immutable')

    def popitem(self):
        raise TypeError(f'{self.__class__.__name__} is immutable')

    def update(self, *v, **kw):
        raise TypeError(f'{self.__class__.__name__} is immutable')

    def clear(self):
        raise TypeError(f'{self.__class__.__name__} is immutable')

    def __hash__(self):
        try:
            ash = self._hash
        except AttributeError:
            self._hash = ash = None
            items = self._hash_items_()
            if items is not None:
                try:
                    self._hash = ash = hash((frozendict, tuple(items)))
                except TypeError as e:
                    raise TypeError(f'unhashable type: {self.__class__.__name__!r}') from e

        if ash is None:
            raise TypeError(f'unhashable type: {self.__class__.__name__!r}')

        return ash

    def _hash_items_(self):
        return ((k, self[k]) for k in sorted(self))

    def __reduce__(self):
        return self.__class__, (self,), 

    def copy(self):
        return self.__class__(self)

    def __deepcopy__(self, memo=None):
        return self.__class__(deepcopy(dict(self), memo))

    def merge(self, arg=(), /, **kwargs):
        ret = self.copy()
        (arg or kwargs) and dict.update(ret, arg, **kwargs)
        return ret

    __copy__ = copy



@export()
class factorydict(frozendict[_T_Key, _T_Val]):

    __slots__ = '__getitem__',

    def __init__(self, func, keys=()) -> None:
        self.__getitem__ = func
        super().__init__(keys and dict.fromkeys(keys))
    
    def __reduce__(self):
        return self.__class__, (self.__getitem__, tuple(self))

    def copy(self):
        return self.__class__(self.__getitem__, self)

    __copy__ = copy

    def items(self):
        return ItemsView[tuple[_T_Key, _T_Val]](self)

    def values(self):
        return ValuesView[_T_Val](self)
    
    def _hash_items_(self):
        return None

    def __hash__(self):
        raise TypeError(f'unhashable type: {self.__class__.__name__!r}')






@export()
class nonedict(factorydict[_T_Key, None], t.Generic[_T_Key]):

    __slots__ = ()

    def __init__(self):
        super().__init__(_none_fn)

    def __len__(self) -> 0:
        return 0
    
    def __copy__(self):
        return self
    
    copy = __copy__

    def __reduce__(self):
        return self.__class__, ()

    def __contains__(self, key: _T_Key) -> False:
        return False

    def __bool__(self) -> False:
        return False

    def __iter__(self):
        if False:
            yield None
        
    def _hash_items_(self):
        return ()



def key_error_fallback(k):
    raise KeyError(k)



class FallbackMappingMixin:

    __slots__ = ()

    _default_fb: t.ClassVar[_FallbackType[_T_Key, _T_Val]] = frozendict()

    @property
    def fallback(self) -> _FallbackType[_T_Key, _T_Val]:
        if self._fallback is None:
            self._initfallback_()
        return self._fallback
    
    @fallback.setter
    def fallback(self, fb: _FallbackType[_T_Key, _T_Val]):
        self._fb = fb
        if hasattr(self, '_fallback'):
            del self._fb_func
        self._fallback = None
        # self._fallback = self._fb_func = None

    def _initfallback_(self):
        if self._fallback is None:
            fb = self._fb
            if fb is None:
                fb = self._default_fb
            
            typ = fb.__class__
            if fb is None:
                self._fallback = nonedict()
            elif issubclass(typ, Mapping):
                self._fallback = fb
            elif issubclass(typ, type):
                if issubclass(fb, Mapping):
                    self._fallback = fb()
                else:
                    self._fallback = factorydict(lambda k: fb())
            elif issubclass(typ, FunctionType):
                if 'self' in fb.__annotations__:
                    self._fallback = factorydict(lambda k: fb(self, k))
                else:
                    self._fallback = factorydict(fb)
            elif isinstance(fb, Callable):
                self._fallback = factorydict(fb)
            else:
                # self.__missing__ = _none_fn
                raise TypeError(f'Fallback must be a Mapping | Callable | None. Got: {type(fb)}')
            self._fb_func = self._fallback.__getitem__

        return self._fb_func

    def __missing__(self, k):
        if fn := self._fb_func:
            return fn(k)
        raise KeyError(k)



@export()
@FluentMapping.register
class fallbackdict(FallbackMappingMixin, dict[_T_Key, _T_Val], t.Generic[_T_Key, _T_Val]):
    """A dict that retruns a fallback value when a missing key is retrived.
    
    Unlike defaultdict, the fallback value will not be set.
    """
    __slots__ = ('_fb', '_fallback', '_fb_func')

    _default_fb: t.ClassVar[_FallbackType[_T_Key, _T_Val]] = nonedict()

    def __init__(self, fallback: _FallbackType[_T_Key, _T_Val]=None, *args, **kwds):
        super().__init__(*args, **kwds)
        self.fallback = fallback

    def __missing__(self, k):
        return self._fb_func(k)

    def __getattr__(self, k: str):
        if k == '_fb_func':
            self._fb_func = None
            return self._initfallback_()
        raise AttributeError(k)        
    
    def __reduce__(self):
        # return self.__class__, (self._fb, super().copy())
        return self.__class__, (self._fb, dict(self))

    def copy(self):
        return self.__class__(self._fb, self)

    __copy__ = copy

    def __delattr__(self, name: str) -> None:
        try:
            super().__delattr__(name)
        except AttributeError:
            pass

    # def __deepcopy__(self, memo=None):
    #     # if self._fb is not self._fbfunc and self._fb is not None:
    #     #     return self.__class__(deepcopy(self._fb, memo), super().__deepcopy__(memo))    
    #     # return self.__class__(self._fb, super().__deepcopy__(memo))
    #     return self.__class__(deepcopy(self._fb, memo), super().__deepcopy__(memo))





@export()
class fallback_default_dict(fallbackdict[_T_Key, _T_Val]):

    __slots__ = ()

    def _initfallback_(self):
        if self._fallback is None:
            func = super()._initfallback_()
            setdefault = self.setdefault
            self._fb_func = lambda k: setdefault(k, func(k))
        return self._fb_func


@export()
class fallback_chain_dict(fallbackdict[_T_Key, _T_Val]):

    _default_fb = fallbackdict

    def get(self, key, default=None) -> t.Union[_T_Val, None]:
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, o) -> bool:
        return super().__contains__(o) or self.fallback.__contains__(o)

    def __iter__(self):
        seen = set()
        for k in self.fallback.__iter__():
            yield k
            seen.add(k)
        
        for k in super().__iter__():
            if k not in seen:
                yield k

    def __len__(self):
        return super().__len__() + len(self.fallback.keys() - self.ownkeys())

    def __bool__(self) -> bool:
        return super().__len__() > 0 or bool(self.fallback)
        
    def __eq__(self, o):
        return o == dict(self)
    
    def __ne__(self, o):
        return not self.__eq__(o)

    def __repr__(self):
        return f'{self.__class__.__name__}({super().__repr__()}, fallback={self.fallback!r})'
    
    def extend(self, *args, **kwds):                # like Django's Context.push()
        '''New ChainMap with a new map followed by all previous maps.
        If no map is provided, an empty dict is used.
        '''
        return self.__class__(self, *args, **kwds)

    def keys(self):
        return KeysView[_T_Key](self)

    def items(self):
        return ItemsView[tuple[_T_Key, _T_Val]](self)

    def values(self):
        return ValuesView[_T_Val](self)


    if t.TYPE_CHECKING:
            
        def ownkeys(self) -> KeysView[_T_Key]:
            ...

        def ownitems(self) -> ItemsView[tuple[_T_Key, _T_Val]]:
            ...

        def ownvalues(self) -> ValuesView[_T_Val]:
            ...

    ownkeys = dict[_T_Key, _T_Val].keys
    ownitems = dict[_T_Key, _T_Val].items
    ownvalues = dict[_T_Key, _T_Val].values








class SizedReversible(Sized, Reversible):
    __slots__ = ()




_dict_keys = type(dict[_T_Key]().keys())

@Sequence.register
class _orderedsetabc(t.Generic[_T_Key]):

    __slots__ = '__data__', '__set__'

    __data__: dict[_T_Key, _T_Key]
    __set__: _dict_keys

    # __class_getitem__ = classmethod(GenericAlias)

    # def __class_getitem__(cls, params):
    #     return GenericAlias(cls, tuple(params) if isinstance(params, (tuple, list)) else (params,))

    def __init__(self, iterable: Iterable[_T_Key]=None):
        self.__data__ = self._init_data_set_(iterable)

    def _init_data_set_(self, iterable: Iterable[_T_Key]):
        if isinstance(iterable, _orderedsetabc):
            return iterable.__data__.copy()
        elif iterable is None:
            return {}
        else:
            return dict.fromkeys(iterable)

    def __setstate__(self, state):
        self.__data__ = state
        
    def __getstate__(self):
        return self.__data__.copy()
        
    def __reduce__(self):
        return self.__class__, (), self.__getstate__()
        
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        if name == '__data__':
            object.__setattr__(self, '__set__', self.__data__.keys())
    
    def __bool__(self) -> bool:
        return bool(self.__data__)

    def __len__(self) -> int:
        return self.__data__.__len__()

    def __iter__(self) -> Iterator[_T_Key]:
        yield from self.__data__

    def __contains__(self, o) -> int:
        return self.__data__.__contains__(o)

    def copy(self):
        return self.__class__(self)
    
    __copy__ = copy

    # def __deepcopy__(self, memo=None):
    #     return self.__class__(deepcopy(self, memo))

    def __and__(self, other):
        if other is self:
            return self.__class__(self)
        elif isinstance(other, Iterable):
            if not isinstance(other, (Set, Mapping)):
                other = set(other)
            return self.__class__(v for v in self if v in other)

        return NotImplemented

    def __rand__(self, other):
        if other is self:
            return self.__class__(self)
        elif isinstance(other, Iterable):
            if not isinstance(other, (Set, Mapping)):
                other = dict.fromkeys(other)
            return self.__class__(v for v in other if v in self)

        return NotImplemented

    def __or__(self, other):
        if other is self:
            return self.__class__(self)
        elif isinstance(other, Iterable):
            clone = self.__class__(self)
            clone.__data__.update(dict.fromkeys(other))
            return clone

        return NotImplemented
        
    def __ror__(self, other):
        if other is self:
            return self.__class__(self)
        elif isinstance(other, Iterable):
            clone = self.__class__(other)
            clone.__data__.update(self.__data__)
            return clone

        return NotImplemented

    def __reversed__(self) -> Iterator[_T_Key]:
        return self.__data__.__reversed__()

    def __sub__(self, other):
        if other is self:
            return self.__class__()
        elif isinstance(other, Iterable):
            if not isinstance(other, (Set, Mapping)):
                other = set(other)
            return self.__class__(v for v in self if v not in other)
            
        return NotImplemented

    def __rsub__(self, other):
        if other is self:
            return self.__class__()
        elif isinstance(other, Iterable):
            if not isinstance(other, (Set, Mapping)):
                other = dict.fromkeys(other)
            return self.__class__(v for v in other if v not in self)

    def __xor__(self, other):
        if other is self:
            return self.__class__()
        elif not isinstance(other, (Set, Mapping)):
            other = dict.fromkeys(other)
            
        return self.__class__(
            i for it in ((v for v in self if v not in other), (v for v in other if v not in self)) for i in it
        )

    def __rxor__(self, other):
        if other is self:
            return self.__class__()
        elif not isinstance(other, (Set, Mapping)):
            other = dict.fromkeys(other)
            
        return self.__class__(
            i for it in ((v for v in other if v not in self), (v for v in self if v not in other)) for i in it
        )

    def __le__(self, other):
        return self.__eq__(other) or self.__lt__(other)

    def __lt__(self, other):
        if other is self:
            return False
        elif isinstance(other, _orderedsetabc):
            other = other.__set__
        return self.__set__.__lt__(other)

    def __gt__(self, other):
        if other is self:
            return False
        elif isinstance(other, _orderedsetabc):
            other = other.__set__
        return self.__set__.__gt__(other)

    def __ge__(self, other):
        return self.__eq__(other) or self.__gt__(other)

    def __eq__(self, other):
        if other is self:
            return True
        elif isinstance(other, _orderedsetabc):
            other = other.__set__
        return self.__set__.__eq__(other)

    def __repr__(self):
        items = tuple(self)
        return f'{self.__class__.__name__}({items})'

    t.overload
    def __getitem__(self, key: int) -> _T_Key:
        ...
    t.overload
    def __getitem__(self: _T_Val, key: slice) -> _T_Val:
        ...
    def __getitem__(self: _T_Val, key: t.Union[int, slice]) -> t.Union[_T_Key, _T_Val]:
        if isinstance(key, int):
            try:
                return next(self._islice_(key, key+1))
            except StopIteration:
                raise IndexError(f'index {key} out of range')
        elif isinstance(key, slice):
            return self.__class__(self._islice_(key.start or 0, key.stop, key.step))
        raise ValueError(key)        

    at = __getitem__

    def index(self, value, start=0, stop=None):
        '''S.index(value, [start, [stop]]) -> integer -- return first index of value.
           Raises ValueError if the value is not present.

           Supporting start and stop arguments is optional, but
           recommended.
        '''
        for i, v in self._islice_(start, stop, enumerate=True):
            if v is value or v == value:
                return i
        
        raise ValueError(value)

    @t.overload
    def _islice_(self, start=0, stop=None, step=None, *, reverse: t.Union[float, bool]=0.501) -> _T_Key:
        ...
    @t.overload
    def _islice_(self, start=0, stop=None, step=None, *, enumerate: bool=False, reverse: t.Union[float, bool]=0.501) -> _T_Key:
        ...
    @t.overload
    def _islice_(self, start=0, stop=None, step=None, *, enumerate: bool=True, reverse: t.Union[float, bool]=0.501) -> tuple[int, _T_Key]:
        ...
    def _islice_(self, start=0, stop=None, step=None, *, enumerate: bool=False, reverse: t.Union[float, bool]=None):
        size = len(self)

        if start is not None and start < 0:
            start = max(size + start, 0)
        
        if stop is None:
            stop = size
        elif stop < 0:
            stop += size

        step = step or 1
        reverse = -1 if reverse is True else 0 if reverse is False \
            else reverse if reverse is not None \
                else -1 if step < 0 else 0.50001 

        step = abs(step)
        _1 = 1 if step > 0 else -1
        n = start or 0
        x = 0

        if reverse and start > size * reverse:
            n, stop = 1 + size - stop, size - (n or 1)
            for val in reversed(self):
                x += 1
                if x == n:
                    yield (size - x, val) if enumerate is True else val
                    n += step
                    if n > stop:
                        break
            
        else:
            for val in self:
                if x == n:
                    yield (x, val) if enumerate is True else val
                    n += step
                    if n >= stop:
                        break
                x += 1
        
    def count(self, value):
        'S.count(value) -> integer -- return number of occurrences of value'
        return 1 if value in self else 0

    @classmethod
    def _from_iterable(cls, it):
        '''Construct an instance of the class from any iterable input.

        Must override this method if the class constructor signature
        does not accept an iterable for an input.
        '''
        return cls(it)

    def isdisjoint(self, other):
        'Return True if two sets have a null intersection.'
        return self.__set__.isdisjoint(other)

    def clear(self):
        """This is slow (creates N new iterators!) but effective."""
        self.__data__.clear()

    def _hash(self):
        """Compute the hash value of a set.

        Note that we don't define __hash__: not all sets are hashable.
        But if you define a hashable set type, its __hash__ should
        call this function.

        This must be compatible __eq__.

        All sets ought to compare equal if they contain the same
        elements, regardless of how they are implemented, and
        regardless of the order of the elements; so there's not much
        freedom for __eq__ or __hash__.  We match the algorithm used
        by the built-in frozenset type.
        """
        MAX = sys.maxsize
        MASK = 2 * MAX + 1
        n = len(self)
        h = 1927868237 * (n + 1)
        h &= MASK
        for x in self:
            hx = hash(x)
            h ^= (hx ^ (hx << 16) ^ 89869747)  * 3644798167
            h &= MASK
        h = h * 69069 + 907133923
        h &= MASK
        if h > MAX:
            h -= MASK + 1
        if h == -1:
            h = 590923713
        return h

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def __modify_schema__(cls, field_schema: dict[str, t.Any]) -> None:
        assign(field_schema, type='array')

    @classmethod
    def validate(cls, v):
        if v is None:
            return None
        elif type(v) is cls:
            return v.copy()
        elif not isinstance(v, Iterable) or isinstance(v, str):
            return cls((v,))
        else:
            return cls(v)
    
    
@export()
@Set.register
class frozenorderedset(_orderedsetabc[_T_Key]):
    
    __slots__ = ()
    
    # def _attr_error(name=''):
        # def err(self):
            # raise AttributeError(f'{name} on immutable {self.__class__}')
        # err.__name__ = name or 'err'
        # return err

    # update = _attr_error('update')
    # pop = _attr_error('pop')
    # add = _attr_error('add')
    # discard = _attr_error('discard')
    # del _attr_error

    __hash__ = _orderedsetabc._hash



@export()
@MutableSet.register
class orderedset(_orderedsetabc[_T_Key], t.Generic[_T_Key]):
    
    __slots__ = ()

    def add(self, value):
        """Add an element."""
        self.__data__[value] = None

    def discard(self, value):
        """Remove an element.  Do not raise an exception if absent."""
        try:
            self.remove(value)
        except KeyError:
            pass

    def remove(self, value):
        """Remove an element. If not a member, raise a KeyError."""
        del self.__data__[value]

    def update(self, *iterables: Iterable[_T_Key]):
        """Add an element."""
        self.__data__.update(dict.fromkeys(k for it in iterables if it is not self for k in it))
    
    # def pop(self, val: _TK = _empty, default=_empty):
    def pop(self):
        """Return the popped value.  Raise KeyError if empty."""
        return self.__data__.popitem()[0]

    def shift(self):
        """Return the popped value.  Raise KeyError if empty."""
        try:
            return next(self.__iter__())
        except StopIteration:
            raise KeyError(f'empty {self.__class__.__name__}')

    def __ior__(self, it):
        it is self or self.update(it)
        return self

    def __iand__(self, it):
        if it is self:
            return self
        elif isinstance(it, Iterable):
            if not isinstance(it, (Set, Mapping)):
                it = set(it)
            self.__data__ = dict.fromkeys(v for v in self if v in it)
            return self

        return NotImplemented

    def __ixor__(self, it):
        if it is self:
            self.clear()
            return self
        elif isinstance(it, Iterable):
            if not isinstance(it, (Set, Mapping)):
                it = set(it)
            self.__data__ = dict.fromkeys(
                i for it in ((v for v in self if v not in it), (v for v in it if v not in self)) for i in it
            )
            return self
        return NotImplemented

    def __isub__(self, it):
        if it is self:
            self.clear()
            return self
        elif isinstance(it, Iterable):
            if not isinstance(it, (Set, Mapping)):
                it = set(it)
            self.__data__ = dict.fromkeys(v for v in self if v not in it)
            return self
        return NotImplemented



_T_Stack_K = t.TypeVar('_T_Stack_K')
_T_Stack_S = t.TypeVar('_T_Stack_S', bound=MutableSequence, covariant=True)
_T_Stack_V = t.TypeVar('_T_Stack_V', bound=Orderable)


class PriorityStack(dict[_T_Stack_K, list[_T_Stack_V]], t.Generic[_T_Stack_K, _T_Stack_V, _T_Stack_S]):
    
    __slots__= ('stackfactory',)

    if t.TYPE_CHECKING:
        stackfactory: Callable[..., _T_Stack_S] = list[_T_Stack_V]

    def __init__(self, _stackfactory: Callable[..., _T_Stack_S]=list, /, *args, **kwds) -> None:
        self.stackfactory = _stackfactory or list
        super().__init__(*args, **kwds)

    @t.overload
    def remove(self, k: _T_Stack_K, val: _T_Stack_V):
        self[k:].remove(val)

    def setdefault(self, k: _T_Stack_V, val: _T_Stack_V) -> _T_Stack_V:
        stack = super().setdefault(k, self.stackfactory())
        stack or stack.append(val)
        return stack[-1]

    def copy(self):
        return self.__class__(self.stackfactory, ((k, self[k:][:]) for k in self))
    
    def __reduce__(self):
        return self.__class__, (self.stackfactory, dict((k, self[k:][:]) for k in self))
    
    __copy__ = copy

    def extend(self):
        return self.__class__(self.stackfactory, self.all_items())
    
    def index(self, k: _T_Stack_K, val: _T_Stack_V, start: int=0, stop: int=None) -> int:
        return super().__getitem__(k).index(val, start, stop)
    
    def insert(self, k: _T_Stack_K, index: t.Optional[int], val: _T_Stack_V, *, sort=True):
        stack = super().setdefault(k, self.stackfactory())
        stack.insert(len(stack) if index is None else index, val)
        sort and stack.sort()
    
    def append(self, k: _T_Stack_K, val: _T_Stack_V, *, sort=True):
        self.insert(k, None, val, sort=sort)
    
    get_all = dict[_T_Stack_K, list[_T_Stack_V]].get
    def get(self, k: _T_Stack_K, default=None):
        try:
            return self[k]
        except (KeyError, IndexError):
            return default

    all_items: Callable[[], ItemsView[_T_Stack_K, list[_T_Stack_V]]] = dict.items
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

    all_values = dict[_T_Stack_K, list[_T_Stack_V]].values
    def values(self):
        return ValuesView[_T_Stack_V](self)
        
    @t.overload
    def __getitem__(self, k: _T_Stack_K) -> _T_Stack_V: ...
    @t.overload
    def __getitem__(self, k: slice) -> _T_Stack_S: ...
    def __getitem__(self, k):
        if isinstance(k, slice):
            return super().__getitem__(k.start)
        else:
            return super().__getitem__(k)[-1]

    def __setitem__(self, k: _T_Stack_K, val: _T_Stack_V):
        self.insert(k, None, val, sort=True)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({{ {", ".join(f"{k!r}: {self[k:]!r}" for k in self) }}})'

    def __str__(self) -> str:
        return f'{self.__class__.__name__}({{ {", ".join(f"{k!r}: {self[k:]!r}" for k in self) }}})'

_none_stack = (None,)

@export()
class FluentPriorityStack(PriorityStack[_T_Stack_K, _T_Stack_V, _T_Stack_S]):
    
    def __missing__(self, k: _T_Stack_K) -> _T_Stack_S:
        return _none_stack
    




################################################################################
### MappingProxy
################################################################################

@Mapping.register
class MappingProxy(FallbackMappingMixin, t.Generic[_T_Key, _T_Val], metaclass=ABCMeta):

    __slots__ = '__data__', '_fb', '_fallback', '_fb_func'

    __data__: Mapping[_T_Key, _T_Val]
    _default_fb = key_error_fallback

    def __new__(cls, mapping: Mapping[_T_Key, _T_Val], *, fallback: _FallbackType[_T_Key, _T_Val]=key_error_fallback, mutable: bool=False):
        if cls is MappingProxy:
            if mutable is True:
                cls = MutableMappingProxy

        self: cls[_T_Key, _T_Val] = object.__new__(cls)
        if isinstance(mapping, cls):
            self.__data__ = mapping.__data__
        else:
            self.__data__ = mapping

        self.fallback = fallback

        return self

    @classmethod
    def _from_args_(cls, mapping, fallback=key_error_fallback, /) -> None:
        return cls(mapping, fallback=fallback)    

    def get(self, k: _T_Key, default: t.Union[_T_Default, None]=None) -> t.Union[_T_Val, _T_Default, None]:
        return self.__data__.get(k, default)
    
    def copy(self):
        return self.__class__(self.__data__, self._fb)

    __copy__ = copy

    def keys(self):
        "D.keys() -> a set-like object providing a view on D's keys"
        return self.__data__.keys()

    def items(self):
        "D.items() -> a set-like object providing a view on D's items"
        return self.__data__.items()

    def values(self):
        "D.values() -> an object providing a view on D's values"
        return self.__data__.values()

    def __eq__(self, other):
        return other == self.__data__

    def __bool__(self) -> bool:
        return not not self.__data__

    def __getitem__(self, k: _T_Key) -> _T_Val:
        try:
            return self.__data__[k]
        except KeyError:
            return self.__missing__(k)
    
    def __missing__(self, k):
        if self._fallback is None:
            return self._initfallback_()(k)
        else:
            return self._fb_func(k)
        # raise KeyError(k)

    def __contains__(self, k: _T_Key) -> bool:
        return k in self.__data__

    def __hash__(self):
        return hash(self.__data__)

    def __reversed__(self):
        return self.__data__.__reversed__()

    def __iter__(self):
        return iter(self.__data__)

    def __len__(self) -> bool:
        return len(self.__data__)

    def __reduce__(self):
        return self.__class__._from_args_, (self.__data__, self._fb), 

    def __deepcopy__(self, memo=None):
        return self.__class__(deepcopy(self.__data__, memo), self._fb)

    def __delitem__(self, k):
        raise TypeError(f'{self.__class__.__name__} is immutable')

    def __setitem__(self, k, v):
        raise TypeError(f'{self.__class__.__name__} is immutable')

    def clear(self):
        raise TypeError(f'{self.__class__.__name__} is immutable')

    def setdefault(self, k, v):
        raise TypeError(f'{self.__class__.__name__} is immutable')

    def pop(self, k, *v):
        raise TypeError(f'{self.__class__.__name__} is immutable')

    def popitem(self):
        raise TypeError(f'{self.__class__.__name__} is immutable')

    def update(self, *v, **kw):
        raise TypeError(f'{self.__class__.__name__} is immutable')




@MutableMapping.register
class MutableMappingProxy(MappingProxy[_T_Key, _T_Val]):

    __slots__ = ()

    __data__: MutableMapping[_T_Key, _T_Val]

    def __delitem__(self, k:_T_Key):
        del self.__data__[k]

    def __setitem__(self, k: _T_Key, v: _T_Val):
        self.__data__[k] = v
    
    def setdefault(self, k: _T_Key, default: t.Union[_T_Default, None]=None) -> t.Union[_T_Val, _T_Default]:
        return self.__data__.setdefault(k, default)

    def pop(self, k: _T_Key, *default: _T_Default) -> t.Union[_T_Val, _T_Default]:
        return self.__data__.pop(k, *default)

    if t.TYPE_CHECKING:
        def pop(self, k: _T_Key, default: _T_Default=...) -> t.Union[_T_Val, _T_Default]:
            ...

    def clear(self):
        return self.__data__.clear()

    def popitem(self):
        return self.__data__.popitem()

    def update(self, *a, **kw):
        return self.__data__.update(*a, **kw)






@export()
class AttributeMapping(MutableMapping[_T_Key, _T_Val], t.Generic[_T_Key, _T_Val]):

    __slots__ = ('__weakref__', '__dict__')

    __dict_class__: t.ClassVar[type[dict[_T_Key, _T_Val]]] = dict 
    __dict__: dict[_T_Key, _T_Val]

    
    __type_cache: t.Final[dict[type[Mapping], type['AttributeMapping']]] = fallbackdict()

    def __init_subclass__(cls) -> None:
        if typ := cls.__dict_class__:
            if issubclass(cls, cls.__type_cache.get(typ) or cls):
                cls.__type_cache[typ] = cls
        super().__init_subclass__()

    def __class_getitem__(cls, params):
        if isinstance(params, (tuple, list)):
            typ = params[0]
        else:
            typ = params
        
        if isinstance(typ, type): 
            if issubclass(typ, cls.__dict_class__):
                kls = cls.__type_cache.get(typ)
                if kls is None:
                    bases = cls, 
                    kls = new_class(
                            f'{typ}{cls.__name__}', bases, None, 
                            lambda ns: ns.update(__dict_class__=typ)
                        )
                cls = kls
            
        return GenericAlias(cls, params)

    def __createdict___(self, args) -> tuple[dict[_T_Key, _T_Val], tuple]:
        cls = self.__class__.__dict_class__
        if not args:
            return cls(), args
        elif args[0].__class__ is cls:
            return args[0].copy(), args[1:]
        else:
            return cls(), args

    def __init__(self, *args, **kwds) -> None:
        dct, args = self.__createdict___(args)
        object.__setattr__(self, '__dict__', dct)
        self.update(*args, **kwds)

    def update(self, *args, **kwds):
        args = (i for a in args if a for i in (a.items() if isinstance(a, Mapping) else a or ()))
        self.__dict__.update(args, **kwds)
        return self
    
    def copy(self):
        return self.__class__(self.__dict__)

    def __bool__(self):
        return True

    def __contains__(self, x):
        return x in self.__dict__

    def __json__(self):
        return self.__dict__

    # def __setattr__(self, key, value):
    #     self.__dict__[key] = value

    def __setitem__(self, key: _T_Key, value: _T_Val):
        self.__dict__[key] = value

    def __getitem__(self, key: _T_Key)-> _T_Val:
        try:
            return self.__dict__[key]
        except KeyError:
            return self.__missing__(key)
    
    def __missing__(self, key):
        raise KeyError(key)

    def __delitem__(self, key):
        del self.__dict__[key]

    def __len__(self):
        return len(self.__dict__)

    def __iter__(self):
        return iter(self.__dict__)

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return f'{self.__class__.__name__}({self})'

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @cached_class_property[Callable[[t.Any], 'AttributeMapping']]
    def validate(cls) -> Callable[[t.Any], 'AttributeMapping']:
        try:
            from djx.schemas import object_parser
        except ImportError:
            def parser(v):
                if isinstance(v, cls):
                    return v
                return cls(v)
        else:
            parser = object_parser(cls.__dict_class__)

        return parser
        
        

_T_Str = t.TypeVar('_T_Str', bound=str)




################################################################################
### UserString
################################################################################
@export()
@_BaseUserStr.register
class UserString(Sequence, t.Generic[_T_Str]):

    __slots__ = '_str',

    __str_class__: t.ClassVar[type[_T_Str]] = str

    _str: _T_Str

    __type_cache: t.Final[dict[type[_T_Str], type['UserString']]] = fallbackdict()

    def __init_subclass__(cls) -> None:
        if typ := cls.__dict__.get('__str_class__'):
            if issubclass(cls, cls.__type_cache[typ] or cls):
                cls.__type_cache[typ] = cls

    def __class_getitem__(cls, params):
        if isinstance(params, (tuple, list)):
            typ = params[0]
        else:
            typ = params
        
        if isinstance(typ, type): 
            if issubclass(typ, cls.__str_class__):
                kls = cls.__type_cache[typ]
                if kls is None:
                    # bases = super().__class_getitem__(cls, params),
                    bases = cls, 
                    kls = new_class(
                            f'{typ}{cls.__name__}', bases, None, 
                            lambda ns: ns.update(__str_class__=typ)
                        )
                
                cls = kls
            
        return super().__class_getitem__(cls, params)

    def __init__(self, seq):
        strcls = self.__str_class__
        if isinstance(seq, strcls):
            self._str = seq
        elif isinstance(seq, UserString):
            self._str = strcls(seq._str)
        else:
            self._str = strcls(seq)

    def __str__(self):
        return self._str[:]

    def __repr__(self):
        return repr(self._str)

    def __int__(self):
        return int(self._str)

    def __float__(self):
        return float(self._str)

    def __complex__(self):
        return complex(self._str)

    def __hash__(self):
        return hash(self._str)

    def __getnewargs__(self):
        return (self._str[:],)

    def __eq__(self, string):
        if isinstance(string, UserString):
            return self._str == string._str
        return self._str == string

    def __lt__(self, string):
        if isinstance(string, UserString):
            return self._str < string._str
        return self._str < string

    def __le__(self, string):
        if isinstance(string, UserString):
            return self._str <= string._str
        return self._str <= string

    def __gt__(self, string):
        if isinstance(string, UserString):
            return self._str > string._str
        return self._str > string

    def __ge__(self, string):
        if isinstance(string, UserString):
            return self._str >= string._str
        return self._str >= string

    def __contains__(self, char):
        if isinstance(char, UserString):
            char = char._str
        return char in self._str

    def __len__(self):
        return len(self._str)

    def __getitem__(self, index):
        return self.__class__(self._str[index])

    def __add__(self, other):
        if isinstance(other, UserString):
            return self.__class__(self._str + other._str)
        elif isinstance(other, str):
            return self.__class__(self._str + other)
        return self.__class__(self._str + self.__str_class__(other))

    def __radd__(self, other):
        if isinstance(other, str):
            return self.__class__(other + self._str)
        return self.__class__(self.__str_class__(other) + self._str)

    def __mul__(self, n):
        return self.__class__(self._str * n)

    __rmul__ = __mul__

    def __mod__(self, args):
        return self.__class__(self._str % args)

    def __rmod__(self, template):
        return self.__class__(self.__str_class__(template) % self)

    # the following methods are defined in alphabetical order:
    def capitalize(self):
        return self.__class__(self._str.capitalize())

    def casefold(self):
        return self.__class__(self._str.casefold())

    def center(self, width, *args):
        return self.__class__(self._str.center(width, *args))

    def count(self, sub, start=0, end=sys.maxsize):
        if isinstance(sub, UserString):
            sub = sub._str
        return self._str.count(sub, start, end)

    def removeprefix(self, prefix, /):
        if isinstance(prefix, UserString):
            prefix = prefix._str
        return self.__class__(self._str.removeprefix(prefix))

    def removesuffix(self, suffix, /):
        if isinstance(suffix, UserString):
            suffix = suffix._str
        return self.__class__(self._str.removesuffix(suffix))

    def encode(self, encoding='utf-8', errors='strict'):
        encoding = 'utf-8' if encoding is None else encoding
        errors = 'strict' if errors is None else errors
        return self._str.encode(encoding, errors)

    def endswith(self, suffix, start=0, end=sys.maxsize):
        return self._str.endswith(suffix, start, end)

    def expandtabs(self, tabsize=8):
        return self.__class__(self._str.expandtabs(tabsize))

    def find(self, sub, start=0, end=sys.maxsize):
        if isinstance(sub, UserString):
            sub = sub._str
        return self._str.find(sub, start, end)

    def format(self, /, *args, **kwds):
        return self._str.format(*args, **kwds)

    def format_map(self, mapping):
        return self._str.format_map(mapping)

    def index(self, sub, start=0, end=sys.maxsize):
        return self._str.index(sub, start, end)

    def isalpha(self):
        return self._str.isalpha()

    def isalnum(self):
        return self._str.isalnum()

    def isascii(self):
        return self._str.isascii()

    def isdecimal(self):
        return self._str.isdecimal()

    def isdigit(self):
        return self._str.isdigit()

    def isidentifier(self):
        return self._str.isidentifier()

    def islower(self):
        return self._str.islower()

    def isnumeric(self):
        return self._str.isnumeric()

    def isprintable(self):
        return self._str.isprintable()

    def isspace(self):
        return self._str.isspace()

    def istitle(self):
        return self._str.istitle()

    def isupper(self):
        return self._str.isupper()

    def join(self, seq):
        return self._str.join(seq)

    def ljust(self, width, *args):
        return self.__class__(self._str.ljust(width, *args))

    def lower(self):
        return self.__class__(self._str.lower())

    def lstrip(self, chars=None):
        return self.__class__(self._str.lstrip(chars))

    maketrans = str.maketrans

    def partition(self, sep):
        return self._str.partition(sep)

    def replace(self, old, new, maxsplit=-1):
        if isinstance(old, UserString):
            old = old._str
        if isinstance(new, UserString):
            new = new._str
        return self.__class__(self._str.replace(old, new, maxsplit))

    def rfind(self, sub, start=0, end=sys.maxsize):
        if isinstance(sub, UserString):
            sub = sub._str
        return self._str.rfind(sub, start, end)

    def rindex(self, sub, start=0, end=sys.maxsize):
        return self._str.rindex(sub, start, end)

    def rjust(self, width, *args):
        return self.__class__(self._str.rjust(width, *args))

    def rpartition(self, sep):
        return self._str.rpartition(sep)

    def rstrip(self, chars=None):
        return self.__class__(self._str.rstrip(chars))

    def split(self, sep=None, maxsplit=-1):
        return self._str.split(sep, maxsplit)

    def rsplit(self, sep=None, maxsplit=-1):
        return self._str.rsplit(sep, maxsplit)

    def splitlines(self, keepends=False):
        return self._str.splitlines(keepends)

    def startswith(self, prefix, start=0, end=sys.maxsize):
        return self._str.startswith(prefix, start, end)

    def strip(self, chars=None):
        return self.__class__(self._str.strip(chars))

    def swapcase(self):
        return self.__class__(self._str.swapcase())

    def title(self):
        return self.__class__(self._str.title())

    def translate(self, *args):
        return self.__class__(self._str.translate(*args))

    def upper(self):
        return self.__class__(self._str.upper())

    def zfill(self, width):
        return self.__class__(self._str.zfill(width))




################################################################################
### Arg & Kwarg Collections
################################################################################


_T_Args = t.TypeVar('_T_Args')
_T_Kwargs = t.TypeVar('_T_Kwargs')



# class ArgTupleMeta(t.NamedTupleMeta):

#     def __new__(cls, typename, bases, ns):
#         pass


# class ArgTuple(t.NamedTuple('ArgKwargSet', args=tuple[_T_Args], kwargs=frozendict[str, _T_Kwargs]), t.Generic[_T_Args, _T_Kwargs]):
#     ...


#  ArgKwargTuple(t.NamedTuple('ArgKwargTuple', args=tuple[_T_Args], kwargs=frozendict[str, _T_Kwargs]))



class KwargDict(frozendict[str, _T_Kwargs]):

    __slots__ = ()

    # def __init__(self, arg=(), /, **kwargs) -> None:
    #     if arg and (typ := arg.__class__) is not self.__class__:
    #         if issubclass(typ, Mapping):
    #             arg = (i for i in arg.items() if  self._check_key(i[0]))
    #         else: 
    #             arg = (i for i in arg if  self._check_key(i[0]))
    #     super().__init__(arg, **kwargs)

    # @classmethod
    # def _check_key(cls, k, *, msg=None, exc=None):
    #     if issubclass(k.__class__, str) and k.isidentifier():
    #         return k

    #     if msg is None:
    #         msg = f'{cls.__name__!r} key must a valid str and identifier not ' \
    #             f'{k.__class__.__name__}({k!r})'

    #     raise (exc or TypeError)(msg)            

    # def merge(self, arg=(), /, **kwargs):
    #     if arg and (typ := arg.__class__) is not self.__class__:
    #         if issubclass(typ, Mapping):
    #             arg = (i for i in arg.items() if  self._check_key(i[0]))
    #         else: 
    #             arg = (i for i in arg if  self._check_key(i[0]))
    #     return super().merge(arg, **kwargs)
        

@export()
class Arguments(t.Generic[_T_Args, _T_Kwargs]):

    __slots__ = '_args', '_kwargs', '_hash',
    
    _args: tuple[_T_Args]
    _kwargs: KwargDict[_T_Kwargs]

    __argsclass__: t.ClassVar[type[tuple[_T_Args]]] = tuple
    __kwargsclass__: t.ClassVar[type[Mapping[str, _T_Kwargs]]] = KwargDict

    def __new__(cls, args: Sequence[_T_Args]=(), kwargs: Mapping[str, _T_Kwargs]=KwargDict()):
        self = object.__new__(cls)
        self._args = cls._make_args(args)
        self._kwargs = cls._make_kwargs(kwargs)
        return self
    
    @classmethod
    def _make_args(cls, args) -> tuple[_T_Kwargs]:
        if isinstance(args, cls.__argsclass__):
            return args
        else:
            return cls.__argsclass__(args or ())


    @classmethod
    def _make_kwargs(cls, kwargs):
        if isinstance(kwargs, cls.__kwargsclass__):
            return kwargs
        else:
            return cls.__kwargsclass__(kwargs or {})

    @classmethod
    def coerce(cls, obj) -> 'Arguments[_T_Args, _T_Kwargs]':
        if obj is None:
            return cls()
        typ = obj.__class__
        if typ is cls:
            return obj
        elif issubclass(typ, tuple):
            return cls(obj)
        elif issubclass(typ, Mapping):
            return cls((), obj)
        elif issubclass(typ, list):
            return cls(*obj)
        elif issubclass(typ, Iterable):
            return cls(obj)
        else:
            raise TypeError(f'values must be tuple, list, Arguments, Iterable, Mapping or None not {typ.__name__}')
    
    @classmethod
    def make(cls, *args: _T_Args, **kwargs: _T_Kwargs):
        return cls(args, kwargs)

    @property
    def args(self):
        return self._args

    @property
    def kwargs(self):
        return self._kwargs

    def extend(self, *iterables: t.Iterable[t.Union[Iterable[_T_Args], Mapping[str, _T_Kwargs], Mapping[t.Union[int, slice], _T_Args]]]):
        args = list()
        kwargs = dict()

        for it in iterables:
            t = it.__class__
            if issubclass(t, Arguments):
                args.extend(it._args)
                kwargs.update(it._kwargs)
            elif issubclass(t, KwargDict):
                kwargs.update(it)
            elif issubclass(t, Mapping):
                if isinstance(next(iter(it), ...), str):
                    kwargs.update(it)
                else:
                    try:
                        for k,v in it.items():
                            if isinstance(k, int):
                                args[k:k+1] = v,
                            else:
                                args[k] = v
                    except TypeError as e:
                        raise
            elif issubclass(t, Iterable):
                args.extend(it)
            else:
                raise TypeError(f"Invalid type {t.__name__!r}. Expected {self.__class__.__name__!r}, 'Mapping' or 'Iterable'")

        if not(args or kwargs):
            return self
        else:
            return self.__class__(self._args + tuple(args), self._kwargs.merge(kwargs))

    def merge(self, *args: _T_Args, **kwargs: _T_Kwargs):
        is_a = bool(args)
        is_kw = bool(kwargs)

        if is_a is False is is_kw:
            return self
        elif is_kw is False:
            return self.__class__(self._args + args, self._kwargs)
        else:
            return self.__class__(self._args + args, self._kwargs.merge(kwargs))

    def replace(self, args: t.Union[Iterable[_T_Args], Mapping[t.Union[int, slice], _T_Args]]=..., kwargs: Mapping[str, _T_Kwargs]=...):
        if args is ... is kwargs:
            return self
        elif args is ...:
            return self.__class__(self._args, kwargs)
        
        if isinstance(args, Mapping):
            _args = list(self._args)
            for k,v in args.items():
                if isinstance(k, int):
                    _args[k:k+1] = v,
                else:
                    _args[k] = v
            # args = tuple(_args)

        if kwargs is ...:
            return self.__class__(args, self._kwargs)
        else:
            return self.__class__(args, kwargs)

    def __bool__(self):
        return bool(self._args or self._kwargs)

    def __len__(self):
        return self._args.__len__() + self._kwargs.__len__()

    def __hash__(self):
        try:
            ash = self._hash
        except AttributeError:
            self._hash = ash = None
            items = self._hash_items_()
            if items is not None:
                try:
                    self._hash = ash = hash((Arguments, tuple(items)))
                except TypeError as e:
                    raise TypeError(f'unhashable type: {self.__class__.__name__!r}') from e

        if ash is None:
            raise TypeError(f'unhashable type: {self.__class__.__name__!r}')

        return ash

    def __reduce__(self):
        return self.__class__, (self._args, self._kwargs),

    def copy(self):
        return self.__class__(self._args, self._kwargs)

    __copy__ = copy

    def _hash_items_(self) -> None:
        return self._args, self._kwargs
    
    def __getitem__(self, key: t.Union[str, int]) -> t.Union[_T_Args, _T_Kwargs]:
        if key.__class__ is int:
            return self.args[key]
        try:
            return self.kwargs[key]
        except KeyError:
            try:
                return self.args[key]
            except IndexError as e:
                raise IndexKeyError(key) from e
            except (TypeError, ValueError) as e:
                raise KeyError(key) from e
            raise KeyError(key)

    def __contains__(self, key: t.Union[str, int]):
        if key.__class__ is int:
            return len(self.args) > key
        else:
            return key in self.kwargs

    def __iter__(self):
        yield from range(len(self._args))
        yield from self._kwargs



class IndexKeyError(IndexError, KeyError):
    ...