import sys
from copy import deepcopy
from functools import wraps
from itertools import chain
from types import GenericAlias
import typing as t
from collections.abc import (
    Hashable, Mapping, MutableMapping, MutableSet, Iterable, Set, MutableSequence, 
    Callable, KeysView, ItemsView, ValuesView, Iterator
)
import warnings





from .utils import export, class_only_method, cached_class_property
from .abc import FluentMapping, Orderable

_empty = object()

_T_Keyed = t.TypeVar('_T_Keyed', bound=Hashable)
_TK = t.TypeVar('_TK', bound=Hashable)
_TV = t.TypeVar('_TV')




def _noop_fn(k=None):
    return k



def _none_fn(k=None):
    return None




_FallbackCallable =  Callable[[_TK], t.Optional[_TV]]
_FallbackMap = Mapping[_TK, t.Optional[_TV]]
_FallbackType =  t.Union[_FallbackCallable[_TK, _TV], _FallbackMap[_TK, _TV], _TV] 

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

    def __init__(self, fallback: _FallbackType[_TK, _TV]=None, *args, **kwds):
        super().__init__(*args, **kwds)
        self.fallback = fallback

    @property
    def fallback(self) -> _FallbackType[_TK, _TV]:
        return self._fb
    
    @fallback.setter
    def fallback(self, fb: _FallbackType[_TK, _TV]):
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
        return self._fbfunc or _none_fn

    def __missing__(self, k: _TK) -> _TV:
        if self._fbfunc is None:
            return self._fb
        else:
            return self._fbfunc(k)
    
    def __reduce__(self):
        return self.__class__, (self._fb, super().copy())

    def copy(self):
        return self.__class__(self._fb, self)

    __copy__ = copy

    def __deepcopy__(self, memo):
        # if self._fb is not self._fbfunc and self._fb is not None:
        #     return self.__class__(deepcopy(self._fb, memo), super().__deepcopy__(memo))    
        # return self.__class__(self._fb, super().__deepcopy__(memo))
        return self.__class__(deepcopy(self._fb, memo), super().__deepcopy__(memo))




#@export()
# @deprecated(fallbackdict)
# class fluentdict(fallbackdict[TK, TV]):
    # """A dict that retruns a fallback value when a missing key is retrived.
    
    # Unlike defaultdict, the fallback value will not be set.
    # """
    # __slots__ = ()

    # def __init__(self, *args: t.Union[Iterable[tuple[TK, TV]], Mapping[TK, TV]], **kwds: TV):
    #     super().__init__(None, *args, **kwds)

    # def __reduce__(self):
    #     return self.__class__, (self,)

    # def copy(self):
    #     return self.__class__(self)

    # __copy__ = copy








class _dictset(dict[_T_Keyed, _T_Keyed], t.Generic[_T_Keyed]):

    __slots__ = ()

    def __init__(self, *iterables: Iterable[_T_Keyed]):
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
class FrozenKeyedSet(_dictset[_T_Keyed], Set[_T_Keyed], t.Generic[_T_Keyed]):
    
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
class KeyedSet(_dictset[_T_Keyed], MutableSet[_T_Keyed], t.Generic[_T_Keyed]):
    
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

    def update(self, *iterables: Iterable[_T_Keyed]):
        """Add an element."""
        super().update((i, i) for it in iterables for i in it)
    
    def pop(self, val: _T_Keyed=_empty, *default):
        """Return the popped value.  Raise KeyError if empty."""
        if val is _empty:
            return self.popitem()[0]
        else:
            return self.pop(val, *default)
     





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




