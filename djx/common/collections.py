from collections import ChainMap
from inspect import signature
import sys
from copy import deepcopy
from functools import cache, wraps
from itertools import chain
from types import GenericAlias
import typing as t
from collections.abc import (
    Hashable, Mapping, MutableMapping, MutableSet, Iterable, Set, Sequence, MutableSequence, 
    Callable, KeysView, ItemsView, ValuesView, Iterator, Sized, Reversible
)
import warnings

from djx.common.utils.saferef import saferef





from .utils import export, class_only_method, cached_class_property, assign
from .abc import FluentMapping, Orderable

_empty = object()

_TK = t.TypeVar('_TK', bound=Hashable)
_TV = t.TypeVar('_TV')




def _noop_fn(k=None):
    return k



def _none_fn(k=None):
    return None




_FallbackCallable =  Callable[[_TK], t.Optional[_TV]]
_FallbackMap = Mapping[_TK, t.Optional[_TV]]
_FallbackType =  t.Union[_FallbackCallable[_TK, _TV], _FallbackMap[_TK, _TV], _TV, None] 

_TF = t.TypeVar('_TF', bound=_FallbackType[t.Any, t.Any])


@export()
@FluentMapping.register
class fallbackdict(dict[_TK, _TV], t.Generic[_TK, _TV]):
    """A dict that retruns a fallback value when a missing key is retrived.
    
    Unlike defaultdict, the fallback value will not be set.
    """
    __slots__ = ('_fb', '_fbfunc')

    _fb: _FallbackType[_TK, _TV]
    _fbfunc: _FallbackCallable[_TK, _TV]
    _default_fallback: t.ClassVar[_FallbackType[_TK, _TV]] = None

    def __init__(self, fallback: _FallbackType[_TK, _TV]=None, *args, **kwds):
        super().__init__(*args, **kwds)
        self.fallback = fallback

    @property
    def fallback(self) -> _FallbackType[_TK, _TV]:
        return self._fb
    
    @fallback.setter
    def fallback(self, fb: _FallbackType[_TK, _TV]):
        if fb is None:
            fb = self._default_fallback

        if fb is None:
            # self._fb, self._fbfunc = None, _none_fn
            self._fb = self._fbfunc = None
        elif isinstance(fb, Mapping):
            self._fb, self._fbfunc = fb, fb.__getitem__
        elif callable(fb):
            self._fb = self._fbfunc = fb
        else:
            self._fb = fb
            self._fbfunc = None
        # else:
            # raise TypeError(f'Fallback must be a Mapping or Callable. Got: {type(fb)}')

    @property
    def fallback_func(self):
        if self._fbfunc is None:
            self._fbfunc = _none_fn
        return self._fbfunc

    def __missing__(self, k: _TK) -> _TV:
        if self._fbfunc is None:
            return self.fallback_func(k)
        else:
            return self._fbfunc(k)
    
    def __reduce__(self):
        return self.__class__, (self._fb, super().copy())

    def copy(self):
        return self.__class__(self._fb, self)

    __copy__ = copy

    # def __deepcopy__(self, memo=None):
    #     # if self._fb is not self._fbfunc and self._fb is not None:
    #     #     return self.__class__(deepcopy(self._fb, memo), super().__deepcopy__(memo))    
    #     # return self.__class__(self._fb, super().__deepcopy__(memo))
    #     return self.__class__(deepcopy(self._fb, memo), super().__deepcopy__(memo))


@cache
def _has_self_arg(val):
    sig = signature(val(), follow_wrapped=False)
    return 'self' in sig.parameters


@export()
class fallback_chain_dict(fallbackdict[_TK, _TV]):

    _default_fallback = fallbackdict
    
    @property
    def fallback(self) -> _FallbackType[_TK, _TV]:
        self._fbfunc is None and self.fallback_func
        return self._fb

    @fallback.setter
    def fallback(self, fb: _FallbackType[_TK, _TV]):
        if fb is None:
            fb = self._default_fallback

        if isinstance(fb, Mapping):
            self._fb = fb
            self._fbfunc = fb.__getitem__
        elif callable(fb):
            self._fb = fb
            self._fbfunc = None
        else:
            raise ValueError('fallback must be provided.')

    @property
    def fallback_func(self):
        if self._fbfunc is None:
            fb = self._fb
            if isinstance(fb, type):
                self._fb = fb()
                self._fbfunc = fb.__getitem__
            elif fb is None:
                self._fbfunc = _none_fn
            else:
                self._fb = fb(self)
                self._fbfunc = self._fb.__getitem__

        return self._fbfunc


    def get(self, key, default=None) -> t.Union[_TV, None]:
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, o) -> bool:
        return super().__contains__(o) or self.fallback.__contains__(o)

    @property
    def parent(self):                          # like Django's Context.pop()
        'New ChainMap from maps[1:].'
        return self.__class__(*self.maps[1:])

    def __iter__(self):
        yield from dict.fromkeys(
            (k for s in (self.fallback.__iter__(), super().__iter__()) for k in s)
        ).__iter__()

    def __len__(self):
        return super().__len__() + len(self.fallback.keys() - super().keys())

    def __bool__(self) -> bool:
        return super().__len__() > 0 or bool(self.fallback)
        
    def __eq__(self, o):
        return o == dict(self)
    
    def __ne__(self, o):
        return not self.__eq__(o)

    def extend(self, *args, **kwds):                # like Django's Context.push()
        '''New ChainMap with a new map followed by all previous maps.
        If no map is provided, an empty dict is used.
        '''
        return self.__class__(self, *args, **kwds)

    def keys(self):
        return KeysView[_TK](self)

    def items(self):
        return ItemsView[tuple[_TK, _TV]](self)

    def values(self):
        return ValuesView[_TV](self)












class SizedReversible(Sized, Reversible):
    __slots__ = ()




# @t.overload
# def enumerate_reversed(obj: SizedReversible[_TV], start=None, stop=0, step=-1) -> tuple[int, _TV]:
#     ...

# def enumerate_reversed(obj: SizedReversible[_TV], *args, **kwds) -> tuple[int, _TV]:
    
#     assert isinstance(obj, SizedReversible), 'must be Sized and Reversible'


#     s = slice(*args, **kwds)
#     start, stop, step = s.start or len(obj), s.stop or 0, s.step or -1

#     it = reversed(obj) 
#     _1 = 1 if step > 0 else -1
#     if step > 0:
#         i = 
#     i = nexti = min(start, len(obj)-1) 

#     for v in it:
#         if i == nexti:
#             yield i, v
#             nexti += step
#             if nexti < stop:
#                 break

#         i += _1





@Sequence.register
class _orderedsetabc:

    __slots__ = '__data__', '__set__'

    __data__: dict[_TK, _TK]
    __set__: Set[_TK]

    __class_getitem__ = classmethod(GenericAlias)

    # def __class_getitem__(cls, params):
    #     return GenericAlias(cls, tuple(params) if isinstance(params, (tuple, list)) else (params,))

    def __init__(self, iterable: Iterable[_TK]=None):
        self.__data__ = self._init_data_set_(iterable)

    def _init_data_set_(self, iterable: Iterable[_TK]):
        if isinstance(iterable, _orderedsetabc):
            return iterable.__data__.copy()
        elif iterable is None:
            return {}
        else:
            return dict.fromkeys(iterable)

    def __setstate__(self, state):
        self.__data__ = state
        
    def __getstate__(self):
        return self.__data__
        
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == '__data__':
            super().__setattr__('__set__', self.__data__.keys())
    
    def __bool__(self) -> bool:
        return bool(self.__data__)

    def __len__(self) -> int:
        return self.__data__.__len__()

    def __iter__(self):
        return self.__data__.__iter__()

    def __contains__(self, o) -> int:
        return self.__data__.__contains__(o)

    def copy(self):
        return self.__class__(self)
    
    __copy__ = copy

    def __deepcopy__(self, memo=None):
        return self.__class__(deepcopy(self, memo))

    def __and__(self, other):
        if not isinstance(other, Iterable):
            return NotImplemented
        return self.__class__(value for value in other if value in self)

    __rand__ = __and__

    def __or__(self, other):
        if not isinstance(other, Iterable):
            return NotImplemented

        return self.__class__(e for s in (self, other) for e in s)

    __ror__ = __or__

    def __reversed__(self):
        return self.__data__.__reversed__()

    def __sub__(self, other):
        if not isinstance(other, (Set, Mapping)):
            if not isinstance(other, Iterable):
                return NotImplemented
            other = self.__class__(other)
        return self.__class__(value for value in self if value not in other)

    def __rsub__(self, other):
        if not isinstance(other, Iterable):
            return NotImplemented
        return self.__class__(value for value in other if value not in self)

    def __xor__(self, other):
        if not isinstance(other, Set):
            if not isinstance(other, Iterable):
                return NotImplemented
            other = self.__class__(other)
        return (self - other) | (other - self)

    def __rxor__(self, other):
        if not isinstance(other, Set):
            if not isinstance(other, Iterable):
                return NotImplemented
            other = self.__class__(other)
        return (other - self) | (self - other)

    def __le__(self, other):
        return self.__set__ <= other 

    def __lt__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return len(self) < len(other) and self.__le__(other)

    def __gt__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return len(self) > len(other) and self.__ge__(other)

    def __ge__(self, other):
        return self.__set__.__ge__(other)

    def __eq__(self, other):
        return self.__set__.__eq__(other)

    def __str__(self):
        return  f'{{{", ".join(repr(k) for k in self.__set__)}}}'

    def __repr__(self):
        return f'{self.__class__.__name__}({", ".join(repr(k) for k in self.__set__)})'

    t.overload
    def __getitem__(self, key: int) -> _TK:
        ...
    t.overload
    def __getitem__(self: _TV, key: slice) -> _TV:
        ...
    def __getitem__(self: _TV, key: t.Union[int, slice]) -> t.Union[_TK, _TV]:
        if isinstance(key, int):
            try:
                return next(self._islice_(key, key+1))
            except StopIteration:
                raise IndexError(f'index {key} out of range')
        elif isinstance(key, slice):
            return self.__class__(self._islice_(key.start, key.stop, key.step))
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
    def _islice_(self, start=0, stop=None, step=None, *, reverse: t.Union[float, bool]=0.501) -> _TK:
        ...
    @t.overload
    def _islice_(self, start=0, stop=None, step=None, *, enumerate: bool=False, reverse: t.Union[float, bool]=0.501) -> _TK:
        ...
    @t.overload
    def _islice_(self, start=0, stop=None, step=None, *, enumerate: bool=True, reverse: t.Union[float, bool]=0.501) -> tuple[int, _TK]:
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
class frozenorderedset(_orderedsetabc[_TK]):
    
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
class orderedset(_orderedsetabc[_TK], t.Generic[_TK]):
    
    __slots__ = ()

    def add(self, value):
        """Add an element."""
        self.__data__[value] = value

    def discard(self, value):
        """Remove an element.  Do not raise an exception if absent."""
        try:
            self.remove(value)
        except KeyError:
            pass

    def remove(self, value):
        """Remove an element. If not a member, raise a KeyError."""
        del self.__data__[value]

    def update(self, *iterables: Iterable[_TK]):
        """Add an element."""
        for it in iterables:
            self.__data__.update((i, None) for i in it)
    
    def pop(self, val: _TK = _empty, default=_empty):
        """Return the popped value.  Raise KeyError if empty."""
        if val is _empty:
            if self.__data__:
                return self.__data__.popitem()[0]
            elif default is _empty:
                raise ValueError
            else:
                return default
        else:
            try:
                del self.__data__[val]
            except KeyError:
                if default is _empty:
                    raise ValueError(val)
                return default
            else:
                return val

    def __ior__(self, it):
        self.update(it)
        return self

    def __iand__(self, it):
        for value in (self - it):
            self.discard(value)
        return self

    def __ixor__(self, it):
        if it is self:
            self.clear()
        else:
            if not isinstance(it, Set):
                it = self._from_iterable(it)
            for value in it:
                if value in self:
                    self.discard(value)
                else:
                    self.add(value)
        return self

    def __isub__(self, it):
        if it is self:
            self.clear()
        else:
            for value in it:
                self.discard(value)
        return self



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
    
    __copy__ = copy

    def extend(self):
        return self.__class__(self.stackfactory, self.all_items())
    
    def index(self, k: _T_Stack_K, val: _T_Stack_V, start: int=0, stop: int=None) -> int:
        return super().__getitem__(k).index(val, start, stop)
    
    def insert(self, k: _T_Stack_K, index: t.Optional[int], val: _T_Stack_V, *, sort=True):
        stack = super().setdefault(k, self.stackfactory())
        index = len(stack) if index is None else index % len(stack) 
        stack.insert(index, val)
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



_none_stack = (None,)

@export()
class FluentPriorityStack(PriorityStack[_T_Stack_K, _T_Stack_V, _T_Stack_S]):
    
    def __missing__(self, k: _T_Stack_K) -> _T_Stack_S:
        return _none_stack
    


_TypeOfTypedDict = type(t.TypedDict('_Type', {}, total=False))


@export()
class AttributeMapping(MutableMapping):

    __slots__ = ('__weakref__', '__dict__')
    
    __dict_class__: t.ClassVar[type[Mapping]] = dict 

    def __createdict___(self, args):
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

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __getitem__(self, key):
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
        
        
        
    


    
# def _ensure_done(func=None, msg=None) -> None:
#     def decorate(fn):
#         if isinstance(fn, str):
#             def method(self: '_lazycollection', *args, **kwds):
#                 self._ensure_done(msg or fn)

#                 for b in self.__class__.mro()[1:]:
#                     if hasattr(b, fn):
#                         return getattr(b, fn)(self, *args, **kwds)
#                 raise AttributeError(fn)
#         else:        
#             @wraps(fn)
#             def method(self: '_lazycollection', *args, **kwds):
#                 self._ensure_done(msg or f'{fn.__name__}()')
#                 return fn(self, *args, **kwds)
#         return method

#     if func is None:
#         return decorate
#     else:
#         return decorate(func)

    
# def _with_collect(func=None) -> None:
#     def decorate(fn):
#         if isinstance(fn, str):
#             def method(self: '_lazycollection', *args, **kwds):
#                 self.collect()

#                 for b in self.__class__.mro()[2:]:
#                     if hasattr(b, fn):
#                         return getattr(b, fn)(self, *args, **kwds)
#                 raise AttributeError(fn)
#         else:        
#             @wraps(fn)
#             def method(self: '_lazycollection', *args, **kwds):
#                 self.collect()
#                 return fn(self, *args, **kwds)
#         return method

#     if func is None:
#         return decorate
#     else:
#         return decorate(func)


# class _LazyIterator:

#     __slots__ = ('_iter', '_fset',)

#     def __init__(self, 
#                 src: t.Union[Iterable[tuple[TK, TV]], Mapping[TK, TV]], 
#                 fset: Callable[[tuple[TK, TV]], t.Any]) -> None:
#         # self._src = src
#         self._iter = src if isinstance(src, Iterator) \
#             else iter(src.items()) if isinstance(src, Mapping) \
#                 else iter(src)
#         self._fset = fset

#     def _push_next(self, nxt):
#         raise NotImplementedError(f'{self.__class__.__name__}._push_next')

#     def __bool__(self) -> bool:
#         if self._iter is None:
#             return False
        
#         try:
#             self.__next__()
#         except StopIteration:
#             return False
#         else:
#             return True
    
#     def __len__(self):
#         return int(self.__bool__())
    
#     def __contains__(self, x) -> bool:
#         while self._iter is not None:
#             try:
#                 k = self.__next__()
#             except StopIteration:
#                 break
#             else:
#                 if k == x:
#                     return True
#         return False

#     def __iter__(self):
#         return self
        
#     def __next__(self):
#         if self._iter is not None:
#             try:
#                 yv = next(self._iter)
#             except StopIteration as e:
#                 self._iter = None
#                 raise e
#             else:
#                 return self._push_next(yv)
#         raise StopIteration()


# class _lazycollection:
    
#     __slots__ = ()

#     _lazy_iterator_cls: t.ClassVar[type[_LazyIterator]]

#     def __init__(self, src: Iterable[TV], *args, **kwds):
#         super().__init__(*args, **kwds)
#         self._src = self._lazy_iterator_cls(src, self._get_src_setter(src))

#     @property
#     def done(self) -> None:
#         return not self._src
    
#     def _get_src_setter(self, src):
#         raise NotImplementedError(f'{self.__class__.__name__}._get_src_setter')
    
#     def collect(self) -> None:
#         if self._src:
#             for _ in self._src: 
#                 continue
#         return self
    
#     def __contains__(self, x) -> bool:
#         if super().__contains__(x):
#             return True
#         else:
#             return x in self._src

#     def __bool__(self):
#         return super().__len__() > 0 or self._src.__bool__()

#     def __len__(self):
#         return super().__len__() or self._src.__len__()
    
#     def __iter__(self) -> Iterator[TV]:
#         yield from  super().__iter__()
#         yield from self._src
        
#     def _ensure_done(self, msg='making any changes') -> None:
#         if not self.done:
#             raise RuntimeError(
#                 f'{self.__class__.__name__} must be resolved before {msg}.'
#             )

#     __eq__ = _with_collect('__eq__')
#     __ne__ = _with_collect('__ne__')
#     __gt__ = _with_collect('__gt__')
#     __ge__ = _with_collect('__ge__')
#     __lt__ = _with_collect('__lt__')
#     __le__ = _with_collect('__le__')

#     __add__ = _with_collect('__add__')
#     __iadd__ = _with_collect('__iadd__')

#     __sub__ = _with_collect('__sub__')
#     __isub__ = _with_collect('__isub__')

#     __concat__ = _with_collect('__concat__')
#     __iconcat__ = _with_collect('__iconcat__')

#     __and__ = _with_collect('__and__')
#     __iand__ = _with_collect('__iand__')

#     __or__ = _with_collect('__or__')
#     __ior__ = _with_collect('__ior__')

#     __xor__ = _with_collect('__xor__')
#     __ixor__ = _with_collect('__ixor__')

#     __lshift__ = _with_collect('__lshift__')
#     __ilshift__ = _with_collect('__ilshift__')

#     __rshift__ = _with_collect('__rshift__')
#     __irshift__ = _with_collect('__irshift__')

#     __matmul__ = _with_collect('__matmul__')
#     __imatmul__ = _with_collect('__imatmul__')

#     __mul__ = _with_collect('__mul__')
#     __imul__ = _with_collect('__imul__')

#     __mod__ = _with_collect('__mod__')
#     __imod__ = _with_collect('__imod__')

#     __inv__ = _with_collect('__inv__')
#     __invert__ = _with_collect('__invert__')

#     __truediv__ = _with_collect('__truediv__')
#     __itruediv__ = _with_collect('__itruediv__')

#     __reduce__ = _with_collect('__reduce__')




# class _LazyDictIterator(_LazyIterator):

#     __slots__ = ()

#     def _push_next(self, nxt):
#         self._fset(*nxt)
#         return nxt[0]


# @export()
# class lazydict(_lazycollection, dict[TK, TV], t.Generic[TK, TV]):

#     __slots__ = ('_src',)

#     _lazy_iterator_cls = _LazyDictIterator

#     def _get_src_setter(self, src):
#         return super().__setitem__

#     def __iter__(self) -> Iterator[TV]:
#         if self._src:
#             seen = set()
#             for k in super().__iter__():
#                 yield k
#                 seen.add(k)

#             for k in self._src:
#                 if k not in seen:
#                     yield k
#                     seen.add(k)
#         else:
#             yield from super().__iter__()

#     def __missing__(self, key) -> TV:
#         if key in self._src:
#             return self[key]
#         raise KeyError(key)
        
#     def copy(self):
#         if self._src:
#             return self.__class__(self._src, **super().copy())
#         return super().copy()

#     __copy__ = copy

#     def get(self, key: TK, default: TV = None) -> TV:
#         try:
#             return self[key]
#         except KeyError:
#             return default

#     def keys(self):
#         return KeysView(self) if self._src else super().keys()

#     def items(self):
#         return ItemsView(self) if self._src else super().items()
    
#     def values(self):
#         return ValuesView(self) if self._src else super().values()
    
#     setdefault = _ensure_done(dict.setdefault)
#     pop = _ensure_done(dict.pop)
#     popitem = _ensure_done(dict.popitem)
#     update = _ensure_done(dict.update)
#     clear = _ensure_done(dict.clear)
    
#     __delitem__ = _ensure_done(dict.__delitem__)
#     __reversed__ = _ensure_done(dict.__reversed__)
#     __setitem__ = _ensure_done(dict.__setitem__)







# class _LazyListIterator(_LazyIterator):
#     __slots__ = ()

#     def _push_next(self, nxt):
#         self._fset(nxt)
#         return nxt



# @export()
# class lazylist(_lazycollection, list[TV], t.Generic[TV]):
#     """lazylist Object"""
#     # __slots__ = ('_src',)
#     __slots__ = ('_src',)

#     _lazy_iterator_cls = _LazyListIterator

#     def _get_src_setter(self, src):
#         return super().append

#     def __getitem__(self, k):
#         if isinstance(k, int):
#             if k >= 0:
#                 lfn = super().__len__
#                 if lfn() <= k:
#                     for x in self._src:
#                         if lfn() > k:
#                             break
#             else:
#                 self.collect()
#             return super().__getitem__(k)
#         elif isinstance(k, slice):
#             if k.stop is None or (k.start or 0) < 0 or k.stop < 0 or (k.step or 0) < 0:
#                 self.collect()
#             else:
#                 lfn = super().__len__

#                 if lfn() <= k.stop:
#                     for x in self._src:
#                         if lfn() > k.stop:
#                             break
#             return super().__getitem__(k)

#     def index(self, val: TV, start: int=None, stop: int=None, /):
#         if None is start is stop:
#             try:
#                 return super().index(val)
#             except IndexError:
#                 start = super().__len__()
#                 if val not in self._src:
#                     raise
#                 return super().index(val, start)
#         else:
#             return self.__getitem__(slice(start, stop)).index(val)
        
#     def copy(self):
#         if self._src:
#             return self.__class__(self._src, super().copy()) 
#         return super().copy()

#     __copy__ = copy

#     append = _ensure_done(list.append)
#     pop = _ensure_done(list.pop)

#     remove = _ensure_done(list.remove)
#     reverse = _ensure_done(list.reverse)
#     clear = _ensure_done(list.clear)
#     insert = _ensure_done(list.insert)

#     __delitem__ = _ensure_done(list.__delitem__)
#     __reversed__ = _ensure_done(list.__reversed__)
#     __setitem__ = _ensure_done(list.__setitem__)





# class _LazySetIterator(_LazyIterator):
#     __slots__ = ()

#     def _push_next(self, nxt):
#         self._fset(nxt)
#         return nxt



# @export()
# class lazyset(_lazycollection, set[TV], t.Generic[TV]):

#     __slots__ = ('_src')

#     _lazy_iterator_cls = _LazySetIterator

#     def _get_src_setter(self, src):
#         return super().add

#     def __iter__(self) -> Iterator[TV]:
#         if self._src:
#             seen = set()
#             for k in super().__iter__():
#                 yield k
#                 seen.add(k)

#             for k in self._src:
#                 if k not in seen:
#                     yield k
#                     seen.add(k)
#         else:
#             yield from super().__iter__()

#     def add(self, element: TV) -> None:
#         self._ensure_done('add()')
#         return super().add(element)

#     discard = _ensure_done(set.discard)
#     remove = _ensure_done(set.remove)
#     pop = _ensure_done(set.pop)
#     clear = _ensure_done(set.clear)




