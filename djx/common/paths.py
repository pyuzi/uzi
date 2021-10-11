import typing as t 
import logging

from types import new_class
from pathlib import PurePosixPath, PurePath

from .collections import UserString, fallbackdict
from .utils import export



_T_Path = t.TypeVar('_T_Path', bound=PurePath)
_T_UriPath = t.TypeVar('_T_UriPath', bound=PurePosixPath)

_path_type = type(PurePath())

logger = logging.getLogger(__name__)

@export()
class PathStr(str, t.Generic[_T_Path]):

    __slots__ = '_path',

    __path_class__: t.ClassVar[type[_T_Path]] = PurePath

    _path: _T_Path

    __type_cache: t.Final[dict[type[_T_Path], type['UserString']]] = fallbackdict()

    def __init_subclass__(cls) -> None:
        if typ := cls.__path_class__:
            if issubclass(cls, cls.__type_cache[typ] or cls):
                cls.__type_cache[typ] = cls
        super().__init_subclass__()

    def __class_getitem__(cls, params):
        if isinstance(params, (tuple, list)):
            typ = params[0]
        else:
            typ = params
        
        if isinstance(typ, type): 
            if issubclass(typ, cls.__path_class__):
                kls = cls.__type_cache[typ]
                if kls is None:
                    bases = cls, 
                    kls = new_class(
                            f'{typ}{cls.__name__}', bases, None, 
                            lambda ns: ns.update(__path_class__=typ)
                        )
                cls = kls
            
        return super(cls, cls).__class_getitem__(params)

    def __new__(cls, *parts):
        if len(parts) == 1:
            path = parts[0]
            if path.__class__ is cls:
                return path
            elif path.__class__ is cls.__path_class__:
                return cls._from_path(path)
        
        return cls._from_parts(parts)
        
    @classmethod
    def _for_path(cls, path):
        self = super().__new__(cls, path)
        self._path = path
        return self
    
    @classmethod
    def _from_parts(cls, args):
        return cls._for_path(cls.__path_class__(*args))
        
    @classmethod
    def _from_path(cls, path: _T_Path):
        return cls._for_path(cls._clone_path(path))
    
    @classmethod
    def _clone_path(cls, path: _T_Path) -> _T_Path:
        return cls.__path_class__._from_parsed_parts(path._drv, path._root, path._parts[:])
    
    @property
    def path(self):
        return self._clone_path(self._path)

    @property
    def parts(self):
        return self._path.parts

    def __reduce__(self):
        return self.__class__, self.parts,
    
    def __copy__(self):
        return self._from_path(self._path)

    def __eq__(self, x) -> bool:
        if isinstance(x, PurePath):
            return self._path == x 
        else:
            return super().__eq__(x)
        
    def __hash__(self):
        return super().__hash__()
        
    def __ne__(self, x) -> bool:
        if isinstance(x, PurePath):
            return self._path != x 
        else:
            return super().__ne__(x)
        
    def __lt__(self, x):
        if isinstance(x, PurePath):
            return self._path < x 
        return super().__lt__(x) 

    def __le__(self, x):
        if isinstance(x, PurePath):
            return self._path <= x 
        return super().__le__(x) 

    def __gt__(self, x):
        if isinstance(x, PurePath):
            return self._path > x 
        return super().__gt__(x) 

    def __ge__(self, x):
        if isinstance(x, PurePath):
            return self._path >= x 
        return super().__ge__(x) 

    def __truediv__(self, key):
        return self._for_path(self._path / key)

    def __rtruediv__(self, key):
        return self._for_path(key / self._path)




@export()
class UriPath(PurePosixPath):

    __slots__ = ()






@export()
class UriPathStr(PathStr[_T_UriPath], t.Generic[_T_UriPath]):

    __slots__ = ()
    __path_class__: t.ClassVar[type[_T_UriPath]] = UriPath




