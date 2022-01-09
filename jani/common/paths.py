from os import altsep
import typing as t 
import logging

from types import new_class
from pathlib import PurePosixPath, PurePath

from collections.abc import Sequence
from jani.common.collections import UserString, fallbackdict
from jani.common.utils import export



_T_Path = t.TypeVar('_T_Path', bound=PurePath, covariant=True)
_T_PathStr = t.TypeVar('_T_PathStr', bound='PathStr', covariant=True)
_T_UriPath = t.TypeVar('_T_UriPath', bound='PureUriPath')
# _T_DotPath = t.TypeVar('_T_DotPath', bound='DotPath')


logger = logging.getLogger(__name__)




class _PathStrParents(Sequence[_T_PathStr, _T_Path]):
    """This object provides sequence-like access to the logical ancestors
    of a path.  Don't try to construct it yourself."""
    __slots__ = '_pathcls', 'parents',

    _pathcls: type[_T_PathStr]
    _parents: Sequence[_T_Path]

    def __init__(self, path: _T_PathStr):
        # We don't store the instance to avoid reference cycles
        self._pathcls = type(path)
        self._parents = path._path.parents
        
    def __len__(self):
        return len(self._parents)

    def __getitem__(self, idx):
        p = self._parents[idx]
        return self._pathcls._for_path(p)

    def __repr__(self):
        return "<{}.parents>".format(self._pathcls.__name__)


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

    @property
    def drive(self):
        """The drive prefix (letter or UNC path), if any."""
        return self._path.drive

    @property
    def root(self):
        """The root of the path, if any."""
        return self._path.root

    @property
    def anchor(self):
        """The concatenation of the drive and root, or ''."""
        return self._path.anchor

    @property
    def name(self):
        """The final path component, if any."""
        return self._path.name

    @property
    def suffix(self):
        """
        The final component's last suffix, if any.

        This includes the leading period. For example: '.txt'
        """
        return self._path.suffix

    @property
    def suffixes(self):
        """
        A list of the final component's suffixes, if any.

        These include the leading periods. For example: ['.tar', '.gz']
        """
        return self._path.suffixes

    @property
    def stem(self):
        """The final path component, minus its last suffix."""
        return self._path.stem

    def with_name(self, name):
        """Return a new path with the file name changed."""
        return self._for_path(self._path.with_name(name))

    def with_stem(self, stem):
        """Return a new path with the stem changed."""
        return self._for_path(self._path.with_stem(stem))

    def with_suffix(self, suffix):
        """Return a new path with the file suffix changed.  If the path
        has no suffix, add given suffix.  If the given suffix is an empty
        string, remove the suffix from the path.
        """
        return self._for_path(self._path.with_suffix(suffix))
        
    def relative_to(self, *other):
        """Return the relative path to another path identified by the passed
        arguments.  If the operation is not possible (because this is not
        a subpath of the other path), raise ValueError.
        """
        # For the purpose of this method, drive and root are considered
        # separate parts, i.e.:
        #   Path('c:/').relative_to('c:')  gives Path('/')
        #   Path('c:/').relative_to('/')   raise ValueError
        return self._for_path(self._path.relative_to(*other))

    def joinpath(self, *args):
        return self._for_path(self._path.joinpath(*args))

    def is_relative_to(self, *other):
        """Return True if the path is relative to another path or False.
        """
        return self._path.is_relative_to(*other)

    @property
    def parent(self):
        """The logical parent of the path."""
        return self._for_path(self._path.parent)

    @property
    def parents(self: _T_PathStr) -> _PathStrParents[_T_PathStr, _T_Path]:
        """A sequence of this path's logical parents."""
        return _PathStrParents(self)

    def is_absolute(self):
        """True if the path is absolute (has both a root and, if applicable,
        a drive)."""
        return self._path.is_absolute()

    def is_reserved(self):
        """Return True if the path contains one of the special names reserved
        by the system, if any."""
        return self._path.is_reserved()

    def match(self, path_pattern):
        """
        Return True if this path matches the given pattern.
        """
        return self._path.match(path_pattern)

    def __bytes__(self):
        """Return the bytes representation of the path.  This is only
        recommended to use under Unix."""
        return bytes(self._path)

    def __reduce__(self):
        return self.__class__, self._path,
    
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
class PureUriPath(PurePosixPath):

    __slots__ = ()






@export()
class UriPathStr(PathStr[_T_UriPath], t.Generic[_T_UriPath]):

    __slots__ = ()
    __path_class__: t.ClassVar[type[_T_UriPath]] = PureUriPath






# class _DotPathFlavour(type(PurePosixPath._flavour)):
#     sep = '|'
#     altsep = PurePosixPath._flavour.sep



# _dot_flavour = _DotPathFlavour()

# @export()
# class DotPath(PurePath):

#     __slots__ = ()

#     _flavour = _dot_flavour

#     def __repr__(self):
#         return "{}({!r})".format(self.__class__.__name__, str(self))





# @export()
# class DotPathStr(PathStr[_T_DotPath], t.Generic[_T_DotPath]):

#     __slots__ = ()
#     __path_class__: t.ClassVar[type[_T_DotPath]] = DotPath




