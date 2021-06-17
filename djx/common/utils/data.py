import re
import typing as t 
from enum import IntFlag

from .functools import export

R = t.TypeVar('R') # Return value
O = t.TypeVar('O') # target object
C = t.TypeVar('C', t.Mapping, t.Sequence) # target collection

K = t.TypeVar('K', str, int, t.Hashable) # Key
P = t.TypeVar('P', str, int, t.Hashable, t.List)



missing = object()

_path_re: re.Pattern = re.compile(r'((?<!\.)\[[^\]]*\])')


class PathFlag(IntFlag):
    IS_ATTR = 1 << 1
    IS_INDEX = 1 << 2
    IS_KEY = 1 << 3

    IS_SEQ = 1 << 4
    IS_MAP = 1 << 5


IS_ATTR = PathFlag.IS_ATTR
IS_INDEX = PathFlag.IS_INDEX
IS_KEY = PathFlag.IS_KEY
IS_ITEM = IS_INDEX | IS_KEY

IS_SEQ = PathFlag.IS_SEQ
IS_MAP = PathFlag.IS_MAP



@export()
def getitem(obj: O, path: P, default: R = missing) -> R:
    

    if obj is None:
        target = missing
        sflag = 0
    else:
        target =  obj

        for sflag, key, seg in _iter_path(path):
            tflag = isinstance(target, t.Mapping) and IS_MAP\
                    or isinstance(target, t.Sequence) and IS_SEQ\
                        or 0
        
            if tflag & IS_SEQ:
                target = _getitem(target, int(key))
            elif tflag & IS_MAP:
                if (nt := _getitem(target, key)) is missing and sflag & IS_ATTR:
                    target = getattr(target, key, missing)
                else:
                    target = nt 
            elif sflag & IS_ATTR:
                target = getattr(target, key, missing)
            else:
                raise TypeError(f'invalid key={key!r} in {type(target)} from item path {path=!r}')
            
            if target is missing:
                break
    
    if target is missing and (target := default) is missing:
        if sflag & IS_ATTR:
            e = AttributeError(f'{key!r}')
        elif sflag & IS_INDEX:
            e = IndexError(f'{key!r}')
        else:
            e = KeyError(f'{key!r}')
        raise KeyError(repr(path)) from e
    return target
    



@export()
def setdefault(obj: O, path: P, value: t.Any, default_factory=dict) -> O:
    
    target = obj
    segments = tuple(_iter_path(path))
    
    for sflag, key, seg in segments[:-1]:
        parent = target
        tflag = isinstance(target, t.Mapping) and IS_MAP\
                or isinstance(target, t.Sequence) and IS_SEQ\
                    or 0
    
        if tflag & IS_SEQ:
            if (target := _getitem(parent, int(key))) is missing:
                if callable(default_factory):
                    parent[int(key)] = target = default_factory()
            # elif key == '':
            #     if callable(default_factory):
            #         parent[len(parent):] = target = type(parent)(default_factory())
        elif tflag & IS_MAP:
            if (target := _getitem(parent, key)) is missing and sflag & IS_ATTR:
                target = getattr(parent, key, missing)
             
            if target is missing:
                if callable(default_factory):
                    parent[key] = target = default_factory()
        elif sflag & IS_ATTR:
            if (target := getattr(parent, key, missing)) is missing:
                if callable(default_factory):
                    setattr(parent, key, (target := default_factory()))
        else:
            raise TypeError(f'invalid key={key!r} in {type(target)} from item path {path=!r}')
        
        if target is missing:
            break
    
    rv = missing
    if target is not missing:
        sflag, key, s = segments[-1]
        tflag = isinstance(target, t.Mapping) and IS_MAP\
                or isinstance(target, t.Sequence) and IS_SEQ\
                    or 0
        if tflag & IS_SEQ:
            if key and (rv := _getitem(target, int(key))) is missing:
                rv = target[int(key)] = value
            elif not key:
                rv = target[len(target):] = type(target)(value)
        elif tflag & IS_MAP:
            if (rv := _getitem(target, key)) is missing and sflag & IS_ATTR:
                rv = getattr(target, key, missing)
            if rv is missing:
                rv = target[key] = value
        elif sflag & IS_ATTR:
            if (rv := getattr(target, key, missing)) is missing:
                setattr(target, key, (rv := value))
        else:
            raise TypeError(f'invalid key={key!r} in {type(target)} from item path {path=!r}')

    if target is missing or rv is missing:
        if sflag & IS_ATTR:
            e = AttributeError(f'{key!r}')
        elif sflag & IS_INDEX:
            e = IndexError(f'{key!r}')
        else:
            e = KeyError(f'{key!r}')
        raise KeyError(f'{path=!r}') from e
    
    return rv
    



@export()
def setitem(obj: O, path: P, value: t.Any, default_factory=dict) -> O:
    
    target = obj
    segments = tuple(_iter_path(path))
    
    for sflag, key, seg in segments[:-1]:
        parent = target
        tflag = isinstance(target, t.Mapping) and IS_MAP\
                or isinstance(target, t.Sequence) and IS_SEQ\
                    or 0
    
        if tflag & IS_SEQ:
            if key != '' and (target := _getitem(parent, int(key))) is missing:
                if callable(default_factory):
                    parent[int(key)] = target = default_factory()
            elif key == '':
                target = default_factory()
                parent[len(parent):] = type(parent)((target,))
        elif tflag & IS_MAP:
            if (target := _getitem(parent, key)) is missing and sflag & IS_ATTR:
                target = getattr(parent, key, missing)
             
            if target is missing:
                if callable(default_factory):
                    parent[key] = target = default_factory()
        elif sflag & IS_ATTR:
            if (target := getattr(parent, key, missing)) is missing:
                if callable(default_factory):
                    setattr(parent, key, (target := default_factory()))
        else:
            raise TypeError(f'invalid key={key!r} in {type(target)} from item path {path=!r}')
        
        if target is missing:
            break
    
    if target is missing:
        if sflag & IS_ATTR:
            e = AttributeError(f'{key!r}')
        elif sflag & IS_INDEX:
            e = IndexError(f'{key!r}')
        else:
            e = KeyError(f'{key!r}')
        raise KeyError(f'{path=!r}') from e
        
    else:
        sflag, key, s = segments[-1]
        tflag = isinstance(target, t.Mapping) and IS_MAP\
                or isinstance(target, t.Sequence) and IS_SEQ\
                    or 0
        if tflag & IS_SEQ:
            if key:
                target[int(key)] = value
            else:
                target[len(target):] = type(target)(value)
        elif tflag & IS_MAP:
            target[key] = value
        elif sflag & IS_ATTR:
            setattr(target, key, value)
        else:
            raise TypeError(f'invalid key={key!r} in {type(target)} from item path {path=!r}')
    return obj
    



def _getitem(obj: C, key: K, default=missing):
    try:
        return obj[key]
    except (KeyError, IndexError):
        return default




def _iter_path(path) -> t.Iterator[t.Tuple[PathFlag, K]]:
    if isinstance(path, str):
        path_ = filter(None, _path_re.split(path))
    elif not isinstance(path, list):
        path_ = (path,)
    else:
        path_ = path

    first = True
    for seg in path_:
        if not isinstance(seg, str):
            yield IS_ITEM if _is_index(seg) else IS_KEY, seg, seg
            continue
        elif seg and seg[0] == '[' and seg[-1] == ']':
            yield IS_ITEM if _is_index(key := seg[1:-1]) else IS_KEY, key, seg
        else:
            for key in seg.lstrip('.').split('.'):
                if not key:
                    raise ValueError(f'Invalid item path {path=!r} at {seg!r}')
                
                fl = IS_ITEM if _is_index(key) else IS_KEY | IS_ATTR
                yield fl, key, key if first else f'.{key}' 

        first = False



def _is_index(value):
    if isinstance(value, str):
        return bool(value and (value.isdigit() or value[0] == '-' and value[1:].isdigit()))
    else:
        return isinstance(value, int)
