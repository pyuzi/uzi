from functools import cache, reduce
import re
import operator as op
import typing as t 
from types import FunctionType, MethodType
from enum import IntFlag, Flag, auto
from collections import ChainMap, defaultdict
from collections.abc import (
    Mapping, MutableMapping, MutableSequence, MutableSet, Sequence, Callable,
    Set, 
)
from ._functools import export

_R = t.TypeVar('_R') # Return value
_O = t.TypeVar('_O') # target object
_C = t.TypeVar('_C', Mapping, Sequence) # target collection

_K = t.TypeVar('_K', str, int, 'KeyPath', t.Hashable) # Key
_P = t.TypeVar('_P', str, int, 'KeyPath', t.Hashable, list[t.Union[str, int, t.Hashable]])

_T_DictListSet = t.TypeVar('_T_DictListSet', Mapping, Sequence, Set)
_T_MutableDictListSet = t.TypeVar('_T_MutableDictListSet', MutableMapping, MutableSequence, MutableSet)


missing = object()

_path_re: re.Pattern = re.compile(r'((?<!\.)\[[^\]]*\])')


class KindOfPath(Flag):
    ATTRIBUTE       = auto()
    INDEX           = auto()
    KEY             = auto()

    ITEM           = INDEX | KEY



class KindOfObject(IntFlag):
    PLAIN          = 0
    MAPPING         = auto()
    SEQUENCE        = auto()



_ATTRIBUTE  = KindOfPath.ATTRIBUTE
_INDEX      = KindOfPath.INDEX
_KEY        = KindOfPath.KEY

_ITEM = _INDEX | _KEY

_SEQUENCE = KindOfObject.SEQUENCE
_MAPPING = KindOfObject.MAPPING



class PathLookupError(LookupError):
    
    lookup_type = 'path'

    def __init_subclass__(cls, lookup='path') -> None:
        cls.lookup_type = lookup
        return super().__init_subclass__()

    def __init__(self, lookup: _K, path: _P=None, source: t.Any=None, target: t.Any=None) -> None:
        self.path = path
        self.lookup = lookup
        self.source = source
        self.target = target

    @property
    def lookup(self):
        return getattr(self, self.lookup_type)
    
    @lookup.setter
    def lookup(self, val):
        return setattr(self, self.lookup_type, val)

    def __str__(self) -> str:
        return f'{self.lookup_type}:{self.lookup!r}' \
            + ('' if self.path is None else f' path: {self.path!r}') \
            + ('' if self.source is None else f' source: {self.source!r}') \
            + ('' if self.target is None else f' at: {self.target!r}')


class AttributePathError(PathLookupError, AttributeError, lookup='name'):
    ...

class IndexPathError(PathLookupError, IndexError, lookup='index'):
    ...

class KeyPathError(PathLookupError, KeyError, lookup='key'):
    ...


@t.overload
def result(obj: Callable[[], _R], *args) -> _R: ...

@t.overload
def result(obj: _R) -> _R: ...

@export()
def result(obj, *args):
    if isinstance(obj, (FunctionType, MethodType, DataPath)):
        return obj(*args)
    return obj



@export()
def assign(obj: _O, *items, **kwds) -> _O:
    if obj is None:
        return obj    

    seen = set()
    for i in reversed(items):
        if i is not None:
            for k, v in (i.items() if isinstance(i, Mapping) else i):
                if k in kwds or k in seen:
                    continue
                setitem(obj, k, v)
                seen.add(k)

    for k, v in kwds.items():
        setitem(obj, k, v)

    return obj



@export()
def merge(target: _T_DictListSet, *sources: _T_DictListSet, list_cls=list, dict_cls=dict, set_cls=set, recursive=True, depth=1024) -> _T_DictListSet:
    if depth > 0:
        if isinstance(target, Set):
            if not isinstance(target, MutableSet):
                target = set_cls(target or ())
            for src in sources:
                if src is not None:
                    target |= set_cls(src)
        elif isinstance(target, Sequence):
            if not isinstance(target, MutableSequence):
                target = list_cls(target or ())
            for src in sources:
                if src is not None:
                    target += list_cls(src)
        elif isinstance(target, Mapping):
            if not isinstance(target, MutableMapping):
                target = dict_cls(target or ())

            if not recursive or depth == 0:
                for src in sources:
                    target.update(src)
            elif depth > 0:
                srcs = [target, *(dict_cls(s) for s in sources if s is not None)]
                seen = set()
                keys = ((i, k) for i, d in enumerate(srcs) for k in d if not(k in seen or seen.add(k)))

                for i, k in keys:
                    target[k] = merge(
                        srcs[i][k],
                        *(v for d in srcs[i+1:] if (v := d.get(k, missing)) is not missing),
                        dict_cls=dict_cls,
                        list_cls=list_cls,
                        set_cls=set_cls,
                        depth=depth-1,
                        recursive=True
                    )
        elif sources:
            return sources[-1]

    return target



@export()
def delitem(obj: _O, path: _P) -> _O:
    popitem(obj, path, None)
    return obj




@export()
def getall(obj: _O, *paths: _P, default: _R = missing, withkeys=False, skip_missing=False):
    for path in paths:
        try:
            val = getitem(obj, path)
        except PathLookupError as e:
            if skip_missing is True:
                continue
            elif default is missing:
                raise e
            elif withkeys is True:
                yield path, default
            else:
                yield default
        else:
            if withkeys is True:
                yield path, val
            else:
                yield val
                

@export()
def getany(obj: _O, *paths: _P, default: _R = missing) -> _R:
    for path in paths:
        try:
            return getitem(obj, path)
        except PathLookupError as e:
            pass
    if default is missing:
        if paths:
            raise e from PathLookupError(None, path, obj)
        else:
            raise PathLookupError(None, path, obj)
            
    return default

    

@export()
def hasany(obj: _O, *paths: _P) -> bool:
    for path in paths:
        try:
            getitem(obj, path)
        except PathLookupError:
            pass
        else:
            return True
    
    return False




@export()
def getitem(obj: _O, path: _P, default: _R = missing) -> _R:
    
    if obj is None:
        target = missing
        sflag = 0
    else:
        target =  obj

        for sflag, key, seg in DataPath(path):
            tflag = isinstance(target, Mapping) and _MAPPING\
                    or isinstance(target, Sequence) and _SEQUENCE\
                        or 0
        
            if tflag & _SEQUENCE and sflag & _INDEX:
                target = _getitem(target, int(key))
            elif tflag & _MAPPING:
                if (nt := _getitem(target, key)) is missing and sflag & _ATTRIBUTE:
                    target = getattr(target, key, missing)
                else:
                    target = nt 
            elif sflag & _ATTRIBUTE:
                target = getattr(target, key, missing)
            else:
                raise TypeError(f'invalid key={key!r} in {type(target)} from item path {path=!r}')
            
            if target is missing:
                break
    
    if target is missing and (target := default) is missing:
        if tflag & _MAPPING:
            raise KeyPathError(key, path, obj)
        elif sflag & _ATTRIBUTE:
            raise AttributePathError(key, path, obj)
        elif sflag & _INDEX:
            raise IndexPathError(key, path, obj)
        else:
            raise KeyPathError(key, path, obj)

    return target
    


@export()
def popitem(obj: _O, path: _P, default: _R = missing) -> _R:
    
    if obj is None:
        target = parent = missing
        sflag = 0
    else:
        target = parent = obj
        for sflag, key, seg in DataPath(path):
            parent = target
            tflag = isinstance(target, Mapping) and _MAPPING\
                    or isinstance(target, Sequence) and _SEQUENCE\
                        or 0
        
            if tflag & _SEQUENCE:
                target = _getitem(target, int(key))
            elif tflag & _MAPPING:
                if (nt := _getitem(target, key)) is missing and sflag & _ATTRIBUTE:
                    target = getattr(target, key, missing)
                else:
                    target = nt 
            elif sflag & _ATTRIBUTE:
                target = getattr(target, key, missing)
            else:
                raise TypeError(f'invalid key={key!r} in {type(target)} from item path {path=!r}')
            
            if target is missing:
                break
    
    if target is missing: 
        if (target := default) is missing:
            if tflag & _MAPPING:
                raise KeyPathError(key, path, obj, parent)
            elif sflag & _ATTRIBUTE:
                raise AttributePathError(key, path, obj, parent)
            elif sflag & _INDEX:
                raise IndexPathError(key, path, obj, parent)
            else:
                raise KeyPathError(key, path, obj, parent)
    elif tflag & _SEQUENCE or tflag & _MAPPING:
        del parent[key]
    else:
        delattr(parent, key)
    
    return target
    



@export()
def setdefault(obj: _O, path: _P, value: t.Any, default_factory=...) -> _R:
    
    target: t.Union[MutableMapping, MutableSequence, _O] = obj
    segments = DataPath(path)

    if default_factory is ...:
        default_factory = dict
    elif not (default_factory is None or callable(default_factory)):
        raise ValueError(f'default_factory must be a callable or None. Got {type(default_factory)}')
    
    
    for sflag, key, seg in segments[:-1]:
        parent = target
        tflag = isinstance(target, Mapping) and _MAPPING\
                or isinstance(target, Sequence) and _SEQUENCE\
                    or 0
    
        if tflag & _SEQUENCE:
            if (target := _getitem(parent, int(key))) is missing:
                if default_factory is not None:
                    target = default_factory()
                    parent.insert(int(key), target)
            # elif key == '':
            #     if default_factory is not None:
            #         parent[len(parent):] = target = type(parent)(default_factory())
        elif tflag & _MAPPING:
            if (target := _getitem(parent, key)) is missing and sflag & _ATTRIBUTE:
                target = getattr(parent, key, missing)
             
            if target is missing:
                if default_factory is not None:
                    parent[key] = target = default_factory()
        elif sflag & _ATTRIBUTE:
            if (target := getattr(parent, key, missing)) is missing:
                if default_factory is not None:
                    setattr(parent, key, (target := default_factory()))
        else:
            raise TypeError(f'invalid key={key!r} in {type(target)} from item path {path=!r}')
        
        if target is missing:
            break
    
    rv = missing
    if target is not missing:
        sflag, key, s = segments[-1]
        tflag = isinstance(target, Mapping) and _MAPPING\
                or isinstance(target, Sequence) and _SEQUENCE\
                    or 0
        if tflag & _SEQUENCE:
            if key != '' and (rv := _getitem(target, int(key))) is missing:
                rv = value
                target.insert(int(key), value)
            elif not key:
                target.append(rv := value)
        elif tflag & _MAPPING:
            if (rv := _getitem(target, key)) is missing and sflag & _ATTRIBUTE:
                rv = getattr(target, key, missing)
            if rv is missing:
                rv = target[key] = value
        elif sflag & _ATTRIBUTE:
            if (rv := getattr(target, key, missing)) is missing:
                setattr(target, key, (rv := value))
        else:
            raise TypeError(f'invalid key={key!r} in {type(target)} from item path {path=!r}')

    if target is missing or rv is missing:
        if tflag & _MAPPING:
            raise KeyPathError(key, path, obj)
        elif sflag & _ATTRIBUTE:
            raise AttributePathError(key, path, obj)
        elif sflag & _INDEX:
            raise IndexPathError(key, path, obj)
        else:
            raise KeyPathError(key, path, obj)
    return rv
    



@export()
def setitem(obj: _O, path: _P, value: t.Any, default_factory=...) -> _O:
    
    target: t.Union[MutableMapping, MutableSequence, _O] = obj
    segments = DataPath(path)

    if default_factory is ...:
        default_factory = dict
    elif not (default_factory is None or callable(default_factory)):
        raise ValueError(f'default_factory must be a callable or None. Got {type(default_factory)}')
    
    
    parent: t.Union[MutableMapping, MutableSequence]
    
    for sflag, key, seg in segments[:-1]:
        parent = target
        tflag = isinstance(target, Mapping) and _MAPPING\
                or isinstance(target, Sequence) and _SEQUENCE

        if tflag & _SEQUENCE:
            if key != '' and (target := _getitem(parent, int(key))) is missing:
                if default_factory is not None:
                    target = default_factory()
                    parent.insert(int(key), target)
            elif key == '' and default_factory is not None:
                target = default_factory()
                parent.append(target)
        elif tflag & _MAPPING:
            if (target := _getitem(parent, key)) is missing and sflag & _ATTRIBUTE:
                target = getattr(parent, key, missing)
             
            if target is missing:
                if default_factory is not None:
                    parent[key] = target = default_factory()
        elif sflag & _ATTRIBUTE:
            if (target := getattr(parent, key, missing)) is missing:
                if default_factory is not None:
                    setattr(parent, key, (target := default_factory()))
        else:
            raise TypeError(f'invalid key={key!r} in {type(target)} from item path {path=!r}')
        
        if target is missing:
            break
    
    if target is missing:
        if tflag & _MAPPING:
            raise KeyPathError(key, path, obj)
        elif sflag & _ATTRIBUTE:
            raise AttributePathError(key, path, obj)
        elif sflag & _INDEX:
            raise IndexPathError(key, path, obj)
        else:
            raise KeyPathError(key, path, obj)
        
    else:
        sflag, key, s = segments[-1]
        tflag = isinstance(target, Mapping) and _MAPPING\
                or isinstance(target, Sequence) and _SEQUENCE\
                    or 0
        if tflag & _SEQUENCE:
            if key == '':
                target.insert(int(key), value)
            else:
                target.append(value)
        elif tflag & _MAPPING:
            target[key] = value
        elif sflag & _ATTRIBUTE:
            setattr(target, key, value)
        else:
            raise TypeError(f'invalid key={key!r} in {type(target)} from item path {path=!r}')
    return obj
    




def _getitem(obj: _C, key: _K, default=missing):
    try:
        return obj[key]
    except (KeyError, IndexError):
        return default


class PathSegment(t.NamedTuple):
    kind: KindOfPath
    value: _K
    source: t.Any




@export()
class DataPath(t.Generic[_R]):

    __slots__ = 'value', '_flags',  'segments', '_hash_',  '__weakref__',

    if t.TYPE_CHECKING:
        class Kind(KindOfPath):
            ...
            
    
    Kind: t.Final[type[KindOfPath]] = KindOfPath
    
    _segment_class = PathSegment


    value: _P
    segments: t.Final[tuple[PathSegment]] # type: ignore
    
    __cache: t.Final[defaultdict[type['DataPath'], dict[_K, 'DataPath[_R]']]] = defaultdict(dict)
    __listkey = type('hashlist')
    __cache_max = 1024

    def __new__(cls, path: _P, *segs: _K):
        if segs:
            ck = path, *segs
            path = list(ck)
        elif issubclass(path.__class__, cls):
            return path
        # elif path.__class__ is list:
            # ck = (cls.__listkey, *path)
        else:
            ck = path

        cache = cls.__cache[cls]
        rv = cache.pop(ck, None)

        if rv is not None:
            cache[ck] = rv
            return rv
        else:
            while len(cache) > cls.__cache_max:
                cache.popitem()
            
            new = super().__new__(cls)
            rv  = cache.setdefault(ck, new)
            
            if rv is new:
                rv.value = path
                scls = cls._segment_class
                rv.segments = tuple(scls(*s) for s in cls._iter_path(path))

        return rv        
    
    # @property
    # def kinds(self):
    #     return reduce(op.or_, (f for s in self.segments))

    def __iter__(self):
        return iter(self.segments)
    
    def __getitem__(self, key):
        return self.segments.__getitem__(key)
        
    def __len__(self):
        return len(self.segments)
            
    def __eq__(self, x):
        return x == self.segments
        
    def __hash__(self):
        try:
            return self._hash_
        except AttributeError:
            self._hash_ = hash(self.segments)
            return self._hash_
        
    def __str__(self):
        return str(self.value)
            
    def __int__(self):
        return int(self.value)
            
    def __repr__(self):
        return f'{self.__class__.__name__}({self.value!r})'

    def default(self, obj: _O, value: _R, default_factory=...) -> _R:
        return setdefault(obj, self, value, default_factory)

    def get(self, obj: _O, default=missing) -> _R:
        return getitem(obj, self, default)

    def __call__(self, obj: _O, *, default=missing) -> _R:
        return result(self.get(obj, default))

    def pop(self, obj: _O, default=missing) -> _R:
        return popitem(obj, self, default)

    def set(self, obj: _O, value: _R, default_factory=...) -> _O:
        return setitem(obj, self, value, default_factory)

    @classmethod
    def _iter_path(cls, path) -> t.Iterator[t.Tuple[KindOfPath, _K]]:
        if issubclass(path.__class__, str):
            path_ = filter(None, _path_re.split(path))
        elif not isinstance(path, list):
            path_ = (path,)
        else:
            path_ = path

        first = True
        for seg in path_:
            if isinstance(seg, DataPath):
                yield from seg
            
            if not isinstance(seg, str):
                yield _ITEM if _is_index(seg) else _KEY, seg, seg
                continue
            elif seg and seg[0] == '[' and seg[-1] == ']':
                yield _ITEM if _is_index(key := seg[1:-1]) else _KEY, key, seg
            else:
                for key in seg.lstrip('.').split('.'):
                    if not key:
                        raise ValueError(f'Invalid item path {path=!r} at {seg!r}')
                    
                    fl = _ITEM if _is_index(key) else _KEY | _ATTRIBUTE
                    yield fl, key, key if first else f'.{key}' 

            first = False



def _is_index(value):
    try:
        int(value)
    except (ValueError, TypeError):
        return False
    else:
        return True
    # if isinstance(value, str):
        
    #     return bool(value and (value.isdigit() or value[0] == '-' and value[1:].isdigit()))
    # else:
    #     return isinstance(value, int)
