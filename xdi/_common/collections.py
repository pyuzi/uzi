import typing as t
from collections import ChainMap
from collections.abc import (
    Hashable,
    ItemsView,
    Iterable,
    Iterator,
    Mapping,
    MutableSequence,
    Sequence,
    ValuesView,
)
from copy import deepcopy
from itertools import chain

import attr


_T_Key = t.TypeVar("_T_Key", bound=Hashable)
_T_Val = t.TypeVar("_T_Val", covariant=True)
_T_Default = t.TypeVar("_T_Default", covariant=True)


class frozendict(dict[_T_Key, _T_Val]):

    __slots__ = ("_hash",)

    def not_mutable(self, *a, **kw):
        raise TypeError(f"immutable type: {self} ")

    __delitem__ = __setitem__ = setdefault = not_mutable
    clear = pop = popitem = update = __ior__ = not_mutable
    del not_mutable

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
                    raise TypeError(
                        f"unhashable type: {self.__class__.__name__!r}"
                    ) from e

        if ash is None:
            raise TypeError(f"unhashable type: {self.__class__.__name__!r}")

        return ash

    def _hash_items_(self):
        return ((k, self[k]) for k in sorted(self))

    def __reduce__(self):
        return (
            self.__class__,
            (self,),
        )

    def copy(self):
        return self.__class__(self)

    def __deepcopy__(self, memo=None):
        return self.__class__(deepcopy(dict(self), memo))

    # def merge(self, arg=(), /, **kwargs):
    #     ret = self.copy()
    #     (arg or kwargs) and dict.update(ret, arg, **kwargs)
    #     return ret

    __copy__ = copy


################################################################################
### multidicts
################################################################################

_T_Seq = MutableSequence[_T_Val]


class SeqMapping(Mapping[_T_Key, _T_Seq], t.Generic[_T_Key, _T_Val]):
    __slots__ = ()

    all_items = dict[_T_Key, _T_Seq].items
    all_values = dict[_T_Key, _T_Seq].values


@SeqMapping.register
class MultiDict(dict[_T_Key, _T_Val]):

    __slots__ = ()

    __seq_class__ = list

    # def count(self, k: _T_Key):
    #     try:
    #         return len(self.__getitems__(k))
    #     except KeyError:
    #         return 0

    def get_all(self, k: _T_Key, default: _T_Default = None):
        try:
            return self.__getitems__(k)[:]
        except KeyError:
            return default

    def get(self, k: _T_Key, default: _T_Default = None):
        try:
            return self[k]
        except KeyError:
            return default

    # def extend(self, arg=None, /, **kwds: Iterable[_T_Val]):
    #     if isinstance(arg, SeqMapping):
    #         items = (arg.all_items(), kwds.items())
    #     elif isinstance(arg, Mapping):
    #         items = (arg.items(), kwds.items())
    #     elif arg is not None:
    #         items = (arg, kwds.items())
    #     else:
    #         items = (kwds.items(),)

    #     newseq = self.__seq_class__
    #     for kv in items:
    #         for k, v in kv:
    #             self._dict_setdefault_(k, newseq()).extend(v)

    # def assign(self, arg=None, /, **kwds: _T_Val):
    #     if isinstance(arg, Mapping):
    #         items = (arg.items(), kwds.items())
    #     elif arg is not None:
    #         items = (arg, kwds.items())
    #     else:
    #         items = (kwds.items(),)

    #     newseq = self.__seq_class__
    #     for k, v in items:
    #         self._dict_setdefault_(k, newseq())[:] = (v,)

    # def replace(self, arg=None, /, **kwds: Iterable[_T_Val]):
    #     if isinstance(arg, SeqMapping):
    #         items = (arg.all_items(), kwds.items())
    #     elif isinstance(arg, Mapping):
    #         items = (arg.items(), kwds.items())
    #     elif arg is not None:
    #         items = (arg, kwds.items())
    #     else:
    #         items = (kwds.items(),)

    #     newseq = self.__seq_class__
    #     for kv in items:
    #         for k, v in kv:
    #             self._dict_setdefault_(k, newseq())[:] = v

    # def update(self, arg=None, /, **kwds):
    #     if isinstance(arg, Mapping):
    #         items = chain(arg.items(), kwds.items())
    #     elif arg is not None:
    #         items = chain(arg, kwds.items())
    #     else:
    #         items = kwds.items()

    #     newseq = self.__seq_class__
    #     for k, v in items:
    #         self._dict_setdefault_(k, newseq()).append(v)

    def items(self):
        return ItemsView[tuple[_T_Key, _T_Val]](self)

    def values(self):
        return ValuesView[_T_Val](self)

    def remove(self, k: _T_Key, val: _T_Val):
        seq = self.__getitems__(k)
        seq.remove(val)
        seq or self._dct_pop_(k)

    def setdefault(self, k: _T_Val, val: _T_Val) -> _T_Val:
        if stack := self._dict_setdefault_(k, self.__seq_class__()):
            return stack[-1]
        stack.append(val)
        return stack[-1]

    all_items = dict[_T_Key, _T_Seq].items
    all_values = dict[_T_Key, _T_Seq].values
    _dct_pop_ = dict[_T_Key, _T_Seq].pop
    _dict_setdefault_ = dict[_T_Key, _T_Seq].setdefault
    __setitems__ = dict[_T_Key, _T_Seq].__setitem__
    __getitems__ = dict[_T_Key, _T_Seq].__getitem__

    def all(self, k: _T_Key) -> Sequence[_T_Val]:
        return self.__getitems__(k)[:]

    def __getitem__(self, k: _T_Key) -> _T_Val:
        try:
            return self.__getitems__(k)[-1]
        except IndexError as e:
            raise KeyError(k) from e

    def __setitem__(self, k: _T_Key, val: _T_Val):
        self._dict_setdefault_(k, self.__seq_class__()).append(val)

    def copy(self):
        return self.__class__((k, v[:]) for k, v in self.all_items())

    def __reduce__(self):
        return self.__class__, ({k: v[:] for k, v in self.all_items()},)

    __copy__ = copy

    # def __repr__(self) -> str:
    #     return f'{self.__class__.__name__}({{ {", ".join(f"{k!r}: {self.__getitems__(k)!r}" for k in self) }}})'
    # __str__ = __repr__

    # def __str__(self) -> str:
    #     return f'{self.__class__.__name__}({{ {", ".join(f"{k!r}: {self.__getitems__(k)!r}" for k in self) }}})'



@SeqMapping.register
class MultiChainMap(ChainMap[_T_Key, _T_Val]):

    __slots__ = ()

    maps: list[MultiDict[_T_Key, _T_Val]]

    __map_class__ = MultiDict

    def __init__(self, *maps: SeqMapping[_T_Key, _T_Val]):
        if not maps:
            self.maps = [self.__map_class__()]
        elif isinstance(maps[-1], SeqMapping):
            self.maps = [*maps]
        else:
            self.maps = [maps[:-1], self.__map_class__(maps[-1])]

    @property
    def parents(self):  # like Django's Context.pop()
        "New MultiChainMap from maps[-1:]."
        return self.__class__(*self.maps[-1:])

    def get_all(self, k: _T_Key, default: _T_Default = None):
        if rv := [*self.__getitems__(k)]:
            return rv
        return default

    def all(self, k: _T_Key) -> Sequence[_T_Val]:
        if rv := [*self.__getitems__(k)]:
            return rv
        return self.__missing__(k)

    def iall(self, k: _T_Key):
        return self.__getitems__(k)

    # def count(self, k: _T_Key):
    #     rv = 0
    #     for m in self.maps:
    #         try:
    #             try:
    #                 rv += m.count(k)
    #             except AttributeError:
    #                 rv += int(k in m)
    #         except KeyError:
    #             pass
    #     return rv

    def __getitems__(self, k: _T_Key) -> Iterator[_T_Val]:
        for m in self.maps:
            try:
                try:
                    yield from m.__getitems__(k)
                except AttributeError:
                    yield m[k]
            except KeyError:
                pass

    def __getitem__(self, key):
        maps = self.maps
        lm, i = len(maps), 0

        while lm + i:
            i -= 1
            try:
                return maps[i][key]  # can't use 'key in mapping' with defaultdict
            except KeyError:
                pass
        return self.__missing__(key)


    def copy(self):
        "New ChainMap or subclass with a new copy of maps[0] and refs to maps[1:]"
        return self.__class__(*self.maps[:-1], self.maps[-1].copy())

    __copy__ = copy
    def __setitem__(self, key, value):
        self.maps[-1][key] = value

    def __delitem__(self, key):
        try:
            del self.maps[-1][key]
        except KeyError:
            raise KeyError(f"Key not found in the first mapping: {key!r}")

    def popitem(self):
        "Remove and return an item pair from maps[0]. Raise KeyError is maps[0] is empty."
        try:
            return self.maps[-1].popitem()
        except KeyError:
            raise KeyError("No keys found in the first mapping.")

    def pop(self, key, *args):
        "Remove *key* from maps[0] and return its value. Raise KeyError if *key* not in maps[0]."
        try:
            return self.maps[-1].pop(key, *args)
        except KeyError:
            raise KeyError(f"Key not found in the first mapping: {key!r}")

    def clear(self):
        "Clear maps[0], leaving maps[1:] intact."
        self.maps[-1].clear()

    # def assign(self, *args, **kwds: _T_Val):
    #     return self.maps[-1].assign(*args, **kwds)

    # def extend(self, *args, **kwds: Iterable[_T_Val]):
    #     return self.maps[-1].extend(*args, **kwds)

    # def replace(self, *args, **kwds: Iterable[_T_Val]):
    #     return self.maps[-1].replace(*args, **kwds)

    def update(self, *args, **kwds: _T_Val):
        return self.maps[-1].update(*args, **kwds)

    def remove(self, k: _T_Key, val: _T_Val):
        self.maps[-1].remove(k, val)

    def __ior__(self, other):
        if isinstance(other, Mapping):
            self.maps[-1] | other
            return self
        return NotImplemented

    def __or__(self, other):
        if isinstance(other, Mapping):
            m = self.copy()
            m.maps[-1] |= other
            return m
        return NotImplemented

    def __ror__(self, other):
        if not isinstance(other, Mapping):
            rv = self.__class__()
            m = rv.maps[-1]
            m |= other
            for child in self.maps:
                m |= child
            return rv
        return NotImplemented


################################################################################
### Arg & Kwarg Collections
################################################################################


_T_Args = t.TypeVar("_T_Args")
_T_Kwargs = t.TypeVar("_T_Kwargs")


@attr.s(slots=True, frozen=True)
class Arguments(t.Generic[_T_Args, _T_Kwargs]):
    args: tuple[_T_Args] = attr.field(default=(), converter=tuple)
    kwargs: frozendict[str, _T_Kwargs] = attr.field(default=frozendict(), converter=frozendict)

    def __bool__(self):
        return not not (self.args or self.kwargs)

    def __iter__(self):
        yield self.args
        yield self.kwargs
        

