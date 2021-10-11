from abc import ABCMeta, abstractmethod
import os
import sys
import typing as t
import warnings
from types import FunctionType, ModuleType
from importlib import import_module
from importlib.util import find_spec

from collections.abc import Mapping, Sequence, Set, Iterator

from ..utils.data import getitem
from ..utils import class_property


__all__ = [
    'import_item', 'import_items'
]


_TN = t.TypeVar('_TN', 'Importable', str)
IT = t.TypeVar('IT')
    
_T_mod = t.Union[str, 'Importable', ModuleType]
_T_qual = t.Union[str, 'Importable']



class Importable(metaclass=ABCMeta):
    
    __slots__ = ()

    __module__: str
    __name__: str
    __qualname__: str

    def __json__(self):
        return ImportName(self)
        

Importable.register(type)
Importable.register(classmethod)
Importable.register(staticmethod)
Importable.register(class_property)
Importable.register(FunctionType)





@Importable.register
class ImportName(str):
    
    __slots__ = ('_module',)

    __module__: str
    __qualname__: str
    __name__: str

    _module: str

    is_module: t.ClassVar[bool] = False
    
    @property
    def _qualname(self):
        return self

    # value = property(_qualname.fget)

    class _Flavor:
        object: type['ObjectName'] = None
        module: type['ModuleName'] = None
        invalid: type['InvalidImportName'] = None


    if t.TYPE_CHECKING:
        def __init_(cls, mod: _T_mod, qual:_T_qual=None):
            ...

    @classmethod
    def _parse_raw(cls, val: str):
        self = str.__new__(ImportName, val)
        self._module = None
        return self

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(
            pattern=r'^[a-zA-Z_]+[a-zA-Z0-9_.]?(?:\:[a-zA-Z_]+[a-zA-Z0-9_]?)?$',
            examples=['foo.bar', 'foo.bar:Baz'],
        )

    @classmethod
    def validate(cls, v):
        if isinstance(v, tuple):
            return cls(*v)
        else:
            return cls(v)

    def __new__(bcls: type[IT], mod: _T_mod, qual:_T_qual=None) -> IT:
        if '_Flavor' not in bcls.__dict__:
            if qual is None and isinstance(mod, bcls):
                return mod
            cls = bcls
        elif qual is None:
            if isinstance(mod, bcls):
                return mod
            elif isinstance(mod, str):
                parts = mod.split(':', 1)
                if len(parts) == 2:
                    cls = bcls._Flavor.object
                    mod, qual = parts
                else:
                    cls = bcls._Flavor.module
            elif isinstance(mod, Importable):
                cls = bcls._Flavor.object 
                qual = getattr(mod, '__qualname__', mod.__name__)
                mod = mod.__module__
            elif isinstance(mod, ModuleType):
                cls = bcls._Flavor.module
                mod = mod.__name__
            elif isinstance(mod, tuple):
                return bcls(*mod)
            else:
                raise ValueError(f'expected {_T_mod} but got {type(mod)}')
        else:
            if not isinstance(mod, str):
                if isinstance(mod, ModuleType):
                    mod = mod.__name__
                elif isinstance(mod, Importable):
                    mod = mod.__module__
                
            if isinstance(qual, str):
                cls = bcls._Flavor.object
            elif isinstance(qual, Importable):
                cls = bcls._Flavor.object
                qual = getattr(qual, '__qualname__', qual.__name__)
            else:
                raise ValueError(f'expected {_T_qual} but got {type(qual)}')

        if cls is None:
            cls = bcls._Flavor.invalid or InvalidImportName

        return cls._parse_raw(mod) if qual is None else cls._parse_raw(mod, qual)

    # @property
    # def base(self):
    #     return self._module

    # @property
    # def stem(self):
    #     return self._qualname

    def parts(self):
        return self._module, self._qualname

    def dotted(self):
        return self.replace(':', '.', 1)

    def __repr__(self):
        return f"{self.__class__.__name__}({super().__repr__()})"
    
    def __gt__(self, o) -> bool:
        if isinstance(o, ImportName):
            return self.parts() > o.parts()
        elif isinstance(o, tuple):
            return self.parts() > o
        elif isinstance(o, (str, Importable)):
            return self.parts() > ImportName(o).parts()
        return super().__gt__(o)
    
    def __ge__(self, o) -> bool:
        return o == self or self.__gt__(o)

    def __lt__(self, o) -> bool:
        if isinstance(o, ImportName):
            return self.parts() < o.parts()
        elif isinstance(o, tuple):
            return self.parts() < o
        elif isinstance(o, (str, Importable)):
            return self.parts() < ImportName(o).parts()
        return super().__lt__(o)
    
    def __le__(self, o) -> bool:
        return o == self or self.__lt__(o)
    
    def __copy__(self) -> bool:
        return self

    def __deepcopy__(self, memo):
        return self

    def __getattr__(self, name):
        if name == '__module__':
            if self._module is not None:
                return str(self._module)
        elif name == '__name__':
            return self.__module__ if self._qualname is None else self._qualname 
        elif name == '__qualname__':
            return self._qualname 

        raise AttributeError(name)
    

class InvalidImportName(ImportName):
    
    __slots__ = ()

    @classmethod
    def _parse_raw(cls, val, qual=None) -> ImportName:
        raise ValueError(f'must be importable. got: {val}')
        


def _resolve_module(mod, pkg=None, start=2, stop=None, step=1):

    if pkg is None:
        for x in range(start, stop or start+(step*8)):
            frm = sys._getframe(x)
            # if getitem(frm, 'f_globals.__name__', __name__) == __name__:
            #     continue

            if pkg := getitem(frm, 'f_globals.__package__', None):
                if pkg != __package__:
                    break
    if pkg:
        mn = mod.partition('.')[2]
        parts = pkg.split('.')
        dots = -(len(mn) - len(mn := mn.lstrip('.'))) or len(parts)
        mod = '.'.join(parts[:dots]) + f'.{mn}'

    return mod




class ModuleName(ImportName):

    __slots__ = ()

    _qualname: None = None

    is_module = True

    @classmethod
    def _parse_raw(cls, mod: str, qual: None=None) -> 'ModuleName':
        self = str.__new__(cls, mod)
        if self[:1] == '.':
            mod = _resolve_module(mod)
            if mod != self:
                self = str.__new__(cls, mod)
        return self


    @property
    def _module(self):
        return self

    value = _module




class ObjectName(ImportName):

    __slots__ = ('_qualname',)

    is_module = False

    @classmethod
    def _parse_raw(cls, mod: str, qual: str=None):
        if qual is None:
            mod, _, qual = mod.partition(':')
            if not qual:
                mod, _, qual = mod.rpartition('.')
            
            if not mod:
                mod = 'builtins'

        rv: cls = str.__new__(cls, f'{mod}:{qual}')
        rv._module = (super()._Flavor.module or ModuleName)(mod)
        rv._qualname = qual
        return rv

    # @property
    # def name(self):
    #     return f'{self._module}.{self._qualname}'


ImportName._Flavor.invalid = InvalidImportName
ImportName._Flavor.module = ModuleName
ImportName._Flavor.object = ObjectName



class ImportRefError(ImportError):
    ...





class ImportRef(ImportName, t.Generic[IT]):

    __slots__ = ()

    # __class_getitem__ = classmethod(GenericAlias)
    
    _module: 'ModuleImportRef'

    class _Flavor:
        object: type['ObjectImportRef'] = None
        module: type['ModuleImportRef'] = None
        invalid: type['InvalidImportRef'] = None

    def module(self, default: IT=...) -> ModuleType:
        if self._module in sys.modules:
            return sys.modules[self._module]
        try:
            return import_module(self._module)
        except ImportError as e:
            if not self._module.startswith(e.name):
                raise
            elif default is ...:
                raise ImportRefError(
                    f'module {self._module!r} not found',
                    name=self._module
                    ) from e
            return default

    def exists(self) -> bool:
        try:
            self.__call__()
            return True
        except ImportRefError:
            return False

    def __call__(self, default: IT=...) -> IT:
        raise NotImplementedError(f'{self.__class__.__qualname__}.__call__')

    # @property
    # def value(self) -> t.Optional[IT]:
    #     return self.module if self._qualname is None else self.object
    


class InvalidImportRef(InvalidImportName, ImportRef):

    __slots__ = ()



class ModuleImportRef(ModuleName, ImportRef[ModuleType]):

    __slots__ = ()

    object: None = None
    __call__ = ImportRef.module

    # def __call__(self, default: IT=...) -> IT:
    #     return self.module(default)



class ObjectImportRef(ObjectName, ImportRef[IT]):

    __slots__ = ()

    def __call__(self, default: IT=...) -> IT:
        rv = getitem(self.module(), self._qualname, default)
        if rv is ...:
            raise ImportRefError(
                f'cannot import name {self._qualname!r} from {str(self._module)!r}',
                name=self._module
            )
        return rv





ImportRef._Flavor.module = ModuleImportRef
ImportRef._Flavor.object = ObjectImportRef
ImportRef._Flavor.invalid = InvalidImportRef



def import_item(import_name: str, package=None, *, default: IT=...) -> IT:
    """Imports an object or module based on a string.
    """
    if not isinstance(import_name, ImportName):
        import_name = ImportName(import_name)

    path, item = import_name.parts()
    # path, sep, item = import_name.partition(':')

    if not item:
        try:
            return import_module(import_name, package=package)
        except ImportError as e:
            if '.' not in (path := import_name.lstrip('.')):
                if default is ... or not e.name.endswith(path):
                    raise e
                return default
            else:
                path, d, item = import_name.rpartition('.')

    try:
        rv = import_module(path, package=package)
    except ImportError as e:
        if default is ... or not e.name.endswith(path.lstrip('.')):
            raise e
        return default
    
    if item:
        try:
            rv = getattr(rv, item)
        except (AttributeError, NameError) as e:
            if default is ...:
                raise NameError(f'{item!r} in module {rv.__name__!r}') from e
            return default
    return rv


def __val(v):
    return v


def import_items(value: t.Union[str, Sequence, Mapping, Iterator, Set], package=None, *, itemfunc=None, default=...):
    if isinstance(value, str):
        return import_item(value, package, default=default)
    
    itemfunc = itemfunc or __val
    if isinstance(value, (tuple, list, set)):
        return type(value)(import_items(itemfunc(v), package, default=default) for v in value)
    elif isinstance(value, Mapping):
        return {k: import_items(itemfunc(v), package, default=default) for k,v in value.items()}
    elif isinstance(value, Sequence):
        return tuple(import_items(itemfunc(v), package, default=default) for v in value)
    elif isinstance(value, Iterator):
        fn = lambda v: import_items(itemfunc(v), package, default=default)
        return map(fn, value)
    elif isinstance(value, Set):
        return set((import_items(itemfunc(v), package, default=default) for v in value))
    return value


# def package_path(module):
# 	if isinstance(module, str):
# 		module = sys.modules.get(module) or import_string(module)
# 	path = getattr(module, name, default)


def module_has_submodule(package, module_name, *, silent=False):
    """See if 'module' is in 'package'."""
    try:
        pkg = import_item(package) if isinstance(package, str) else package
        pkg_name = pkg.__name__
        # pkg_path = pkg.__path__
    except (AttributeError, ImportError) as e:
        if not silent:
            raise ValueError('%r is not a valid package.' % (package,)) from e
        return False

    return find_spec(module_name, pkg_name) is not None



def module_dir(module):
    """Find the name of the directory that contains a module, if possible.

    Raise ValueError otherwise, e.g. for namespace packages that are split
    over several directories.
    """
    # Convert to list because _NamespacePath does not support indexing on 3.3.
    paths = list(getattr(module, '__path__', []))
    if len(paths) == 1:
        return paths[0]
    else:
        filename = getattr(module, '__file__', None)
        if filename is not None:
            return os.path.dirname(filename)
    raise ValueError("Cannot determine directory containing %s" % module)




class ModuleMovedDeprecationWarning(DeprecationWarning):
    pass

warnings.simplefilter('always', ModuleMovedDeprecationWarning)


class PlaceHolderImporter(object):
    """This importer redirects imports from this submodule to other locations.
    This makes it possible to continue using objects that have been moved. This
    way, it gives you a smooth time to make your transition.
    """

    def __init__(self, module_choices, wrapper_module, new_location=None, old_location=None, warn=False):
        self.module_choices = module_choices
        self.wrapper_module = wrapper_module
        self.prefix = wrapper_module + '.'
        self.prefix_cutoff = wrapper_module.count('.') + 1
        self.new_location = new_location
        self.old_location = old_location or wrapper_module
        self.warn = warn

    def __eq__(self, other):
        return self.__class__.__module__ == other.__class__.__module__ and \
                self.__class__.__name__ == other.__class__.__name__ and \
                self.wrapper_module == other.wrapper_module and \
                self.module_choices == other.module_choices

    def __ne__(self, other):
        return not self.__eq__(other)

    def install(self):
        sys.meta_path[:] = [x for x in sys.meta_path if self != x] + [self]

    def find_module(self, fullname, path=None):
        if fullname.startswith(self.prefix):
            return self

    def load_module(self, fullname):
        if fullname in sys.modules:
            return sys.modules[fullname]

        modname = fullname.split('.', self.prefix_cutoff)[self.prefix_cutoff]

        if self.warn:
            warnings.warn(
                'Module {o} has been moved to new location {n}. '\
                'Importing {o}.{x} is deprecated, use {n}.{x} instead.'\
                .format(x=modname, o=self.old_location, n=self.new_location),
                ModuleMovedDeprecationWarning, stacklevel=2
            )

        for path in self.module_choices:
            realname = path % modname
            try:
                __import__(realname)
            except ImportError:
                exc_type, exc_value, tb = sys.exc_info()
                # since we only establish the entry in sys.modules at the
                # very this seems to be redundant, but if recursive imports
                # happen we will call into the move import a second time.
                # On the second invocation we still don't have an entry for
                # fullname in sys.modules, but we will end up with the same
                # fake module name and that import will succeed since this
                # one already has a temporary entry in the modules dict.
                # Since this one "succeeded" temporarily that second
                # invocation now will have created a fullname entry in
                # sys.modules which we have to kill.
                sys.modules.pop(fullname, None)

                # If it's an important traceback we reraise it, otherwise
                # we swallow it and try the next choice.  The skipped frame
                # is the one from __import__ above which we don't care about
                if self.is_important_traceback(realname, tb):
                    _reraise(exc_type, exc_value, tb.tb_next)
                continue
            module = sys.modules[fullname] = sys.modules[realname]
            if '.' not in modname:
                setattr(sys.modules[self.wrapper_module], modname, module)

            return module
        raise ImportError('No module named %s' % fullname)

    def is_important_traceback(self, important_module, tb):
        """Walks a traceback's frames and checks if any of the frames
        originated in the given important module.  If that is the case then we
        were able to import the module itself but apparently something went
        wrong when the module was imported.  (Eg: import of an import failed).
        """
        while tb is not None:
            if self.is_important_frame(important_module, tb):
                return True
            tb = tb.tb_next
        return False

    def is_important_frame(self, important_module, tb):
        """Checks a single frame if it's important."""
        g = tb.tb_frame.f_globals
        if '__name__' not in g:
            return False

        module_name = g['__name__']

        # Python 2.7 Behavior.  Modules are cleaned up late so the
        # name shows up properly here.  Success!
        if module_name == important_module:
            return True

        # Some python versions will clean up modules so early that the
        # module name at that point is no longer set.  Try guessing from
        # the filename then.
        filename = os.path.abspath(tb.tb_frame.f_code.co_filename)
        test_string = os.path.sep + important_module.replace('.', os.path.sep)
        return test_string + '.py' in filename or \
               test_string + os.path.sep + '__init__.py' in filename



def _reraise(tp, value, tb=None):
    if value.__traceback__ is not tb:
        raise value.with_traceback(tb)
    raise value
