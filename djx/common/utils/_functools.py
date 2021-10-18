from __future__ import annotations

import sys
import types


import typing as t
from collections.abc import Callable
from warnings import warn
from threading import RLock
from functools import (
    update_wrapper, wraps, cache, 
    cached_property as base_cached_property
)





NOTHING = object()

_T = t.TypeVar('_T')


def noop(*a, **kw):
    pass


def export(obj: _T =..., /, *, name=None, exports=None, module=None) -> _T:
    
    if module is None:
        module = calling_scope().get('__name__')

    def add_to_all(_obj: _T) -> _T:
        _module = sys.modules[module or _obj.__module__]
        _exports = exports or getattr(_module, '__all__', None)
        if _exports is None:
            _exports = []
            setattr(_module, '__all__', _exports)
        _exports.append(name or _obj.__name__)
        return _obj
    return add_to_all if obj is ... else add_to_all(obj)


class class_only_method(classmethod):
    """Creates a classmethod available only to the class. Raises AttributeError
    when called from an instance of the class.
    """

    def __init__(self, func, name=None):
        super().__init__(func)
        self.__name__ = name or func.__name__

    def __get__(self, obj, cls):
        if obj is not None:
            raise AttributeError('Class method {}.{}() is available only to '
                                 'the class, and not it\'s instances.'
                                 .format(cls.__name__, self.__name__))
        return super().__get__(cls, cls)



class class_only_property(classmethod, t.Generic[_T]):
    """Creates a classmethod available only to the class. Raises AttributeError
    when called from an instance of the class.
    """

    def __init__(self, func: Callable[[t.Any], _T], name=None):
        super().__init__(func)
        self.__name__ = name or func.__name__

    def __get__(self, obj, cls) -> _T:
        if obj is not None:
            raise AttributeError(
                f"{cls.__name__}.{self.__name__} is available "
                f"only to the class, and not it's instances."
            )
        return super().__get__(cls, cls)()





class class_property(property, t.Generic[_T]):
    """A decorator that converts a function into a lazy class property."""
    # __slots__ = ()    
    def __get__(self, obj, cls) -> _T:
        return super().__get__(cls, cls)
    


class cached_class_property(class_property[_T]):
    """A decorator that converts a function into a lazy class property."""

    # if t.TYPE_CHECKING:
    #     fget = cache(lambda v: v)

    def __init__(self, func: t.Callable[..., _T]):
        super().__init__(cache(func))
    
    

# class cached_class_property(class_property[T]):
#     """A decorator that converts a function into a lazy class property."""

#     def __init__(self, func: t.Callable[..., T]):
#         super().__init__(func)
#         self.lock = RLock()
#         self.cache = weakref.WeakKeyDictionary()

#     def __get__(self, obj, cls) -> T:

#         # if self.has_cache_value(cls):
#         #     return self.get_cache_value(cls)

#         with self.lock:
#             if self.has_cache_value(cls):
#                 return self.get_cache_value(cls)
#             else:
#                 rv = super().__get__(obj, cls)
#                 self.set_cache_value(cls, rv)
#                 return rv
                
#     def get_cache_value(self, cls, default=...) -> T:
#         return self.cache[cls]

#     def has_cache_value(self, cls) -> bool:
#         return cls in self.cache

#     def set_cache_value(self, cls, value: T):
#         self.cache[cls] = value


def _noop(*a):
    pass



if t.TYPE_CHECKING:
    _bases = property[_T],
else:
    _bases = base_cached_property[_T], property



class cached_property(base_cached_property[_T], property):
    """Transforms a method into property whose value is computed once. 
    The computed value is then cached as a normal attribute for the life of the 
    instance::

            class Foo(object):

                    @cached_property
                    def foo(self):
                            # calculate something important here
                            return 42

    To make the property mutable, set the `readonly` kwarg to `False` or provide
    setter function. If `readonly` is `False` and no setter is provided, it 
    behaves like a normal attribute when a value is set

    Therefore setting `readonly` to `False`:: 

            class Foo(object):

                    @cached_property(readonly=False).getter
                    def foo(self):
                            ...

    Is equivalent to:: 

            class Foo(object):

                    @cached_property
                    def foo(self):
                            ...

                    @foo.setter
                    def foo(self, value):
                            self.__dict__['foo'] = value

    By default: `del obj.attribute` deletes the cached value if present. Otherwise
    an AttributeError is raised. 
    The class has to have a `__dict__` in order for this property to work. 
    """

    func: Callable[[t.Any], _T]
    fget: Callable[[t.Any], _T] = None
    _fset = None
    fset = None
    _fdel = None
    fdel = None
    

    def __init__(self, fget: Callable[[t.Any], _T]=_noop, /, fset=None, fdel=None, *, readonly=False):
        super().__init__(fget)
        self._fset = None
        self.fset = None
        self._fdel = None
        self.fdel = None
        readonly or self.deleter(fdel)
        readonly or self.setter(fset)

    def getter(self, func: Callable[[t.Any], _T]):
        self.func = func
        self.__doc__ = func.__doc__
        return self

    def setter(self, func: Callable[[t.Any, _T]]=None):
        self._fset = func
        self.fset = self._get_fset(func)
        return self

    def deleter(self, func=None):
        self._fdel = func
        self.fdel = self._get_fdel(func)
        return self

    if t.TYPE_CHECKING:
        def __get__(self, obj, typ = None) -> _T:
            ...   

    def __set__(self, instance, val: _T):
        if not callable(self.fset):
            raise AttributeError(
                f'can\'t set readonly attribute {self.attrname!r}'
                f' on {type(instance).__name__!r}.'
            )
        with self.lock:
            self._fset is None or instance.__dict__.pop(self.attrname, None)
            self.fset(instance, val)

    def __delete__(self, instance):
        if not callable(self.fdel):
            raise AttributeError(
                f'can\'t delete attribute {self.attrname!r}'
                f' on {type(instance).__name__!r}.'
            )
        with self.lock:
            self._fdel is None or instance.__dict__.pop(self.attrname, None)
            self.fdel(instance)

    def _get_fset(self, func=None):
        if func is not None:
            return func

        descriptor = self

        def fset(self, val):
            attrname = descriptor.attrname

            assert attrname is not None, (
                "Cannot use cached_property instance without calling __set_name__ on it."
            )

            try:
                self.__dict__[attrname] = val
            except TypeError:
                raise TypeError(
                    f"The '__dict__' attribute on {type(self).__name__!r} instance "
                    f"does not support item assignment for {attrname!r} property."
                ) from None

            except AttributeError:
                raise TypeError(
                    f"No '__dict__' attribute on {type(self).__name__!r} "
                    f"instance to cache {attrname!r} property."
                ) from None

        fset.descriptor = descriptor
        return fset

    def _get_fdel(self, func=None):
        if func is not None:
            return func

        descriptor = self

        def fdel(self):
            attrname = descriptor.attrname

            assert attrname is not None, (
                "Cannot use cached_property instance without calling __set_name__ on it."
            )

            try:
                del self.__dict__[attrname]
            except KeyError:
                pass
                # raise AttributeError(
                #     f'can\'t delete attribute {attrname!r}'
                #     f' on {type(self).__name__!r}.'
                # ) from None
            except TypeError:
                raise TypeError(
                    f"The '__dict__' attribute on {type(self).__name__!r} instance "
                    f"does not support item assignment for {attrname!r} property."
                ) from None

            except AttributeError:
                raise TypeError(
                    f"No '__dict__' attribute on {type(self).__name__!r} "
                    f"instance to cache {attrname!r} property."
                ) from None


        return fdel
    
    def __getstate__(self):
        rv = dict(self.__dict__)
        del rv['lock']
        return rv
    
    def __setstate__(self, state):
        self.__dict__.update(state, lock=RLock())
        

if t.TYPE_CHECKING:
    class cached_property(property[_T], cached_property[_T]):
        ...



def method_decorator(decorator, name=''):
    """
    Convert a function decorator into a method decorator
    """
    # 'obj' can be a class or a function. If 'obj' is a function at the time it
    # is passed to _dec,  it will eventually be a method of the class it is
    # defined on. If 'obj' is a class, the 'name' is required to be the name
    # of the method that will be decorated.
    def _dec(obj):
        is_class = isinstance(obj, type)
        if is_class:
            if name and hasattr(obj, name):
                func = getattr(obj, name)
                if not callable(func):
                    raise TypeError(
                        "Cannot decorate '{0}' as it isn't a callable "
                        "attribute of {1} ({2})".format(name, obj, func)
                    )
            else:
                raise ValueError(
                    "The keyword argument `name` must be the name of a method "
                    "of the decorated class: {0}. Got '{1}' instead".format(
                        obj, name,
                    )
                )
        else:
            func = obj

        def decorate(function):
            """
            Apply a list/tuple of decorators if decorator is one. Decorator
            functions are applied so that the call order is the same as the
            order in which they appear in the iterable.
            """
            if hasattr(decorator, '__iter__'):
                for dec in decorator[::-1]:
                    function = dec(function)
                return function
            return decorator(function)

        def _wrapper(self, *args, **kwargs):
            @decorate
            def bound_func(*args2, **kwargs2):
                return func.__get__(self, type(self))(*args2, **kwargs2)
            # bound_func has the signature that 'decorator' expects i.e.  no
            # 'self' argument, but it is a closure over self so it can call
            # 'func' correctly.
            return bound_func(*args, **kwargs)
        # In case 'decorator' adds attributes to the function it decorates, we
        # want to copy those. We don't have access to bound_func in this scope,
        # but we can cheat by using it on a dummy function.

        @decorate
        def dummy(*args, **kwargs):
            pass
        update_wrapper(_wrapper, dummy)
        # Need to preserve any existing attributes of 'func', including the name.
        update_wrapper(_wrapper, func)

        if is_class:
            setattr(obj, name, _wrapper)
            return obj

        return _wrapper
    # Don't worry about making _dec look similar to a list/tuple as it's rather
    # meaningless.
    if not hasattr(decorator, '__iter__'):
        update_wrapper(_dec, decorator)
    # Change the name to aid debugging.
    if hasattr(decorator, '__name__'):
        _dec.__name__ = 'method_decorator(%s)' % decorator.__name__
    else:
        _dec.__name__ = 'method_decorator(%s)' % decorator.__class__.__name__
    return _dec



__LookupBases = (property,) # if t.TYPE_CHECKING else ()
_T_Look = t.TypeVar('_T_Look')

def _selflookup(obj):
    return obj

class lookup_property(*__LookupBases, t.Generic[_T_Look]):
    """Baseclass for `environ_property` and `header_property`."""
    # read_only = True

    __slots__ = (
        'name', 'src', 
        'default', 'read_only', 'doc',
        'fget', 'fset', 'fdel', 'flook'
    )

    # def __subclasscheck__(self, subclass: type) -> bool:
    #     return super().__subclasscheck__(subclass)

    def __init__(self, name=..., source='self', 
                default=..., *, read_only=False, 
                fget=None, fset=None, fdel=None, doc=None):

        if name is not ...:
            self.name = name

        self.looker(source)
        self.getter(fget)
        self.setter(fset)
        self.deleter(fdel)

        self.doc = doc
        self.default = default
        self.read_only = read_only
    
    @property
    def __doc__(self):
        return self.doc

    def __set_name__(self, owner, name):
        if not hasattr(self, 'name'):
            self.name = name

    def __get__(self, obj, type=None) -> _T_Look:
        if obj is None:
            return self

        from .data import getitem
        
        rv = getitem(self.flook(obj), self.name, self.default)
        
        if rv is ...:
            raise AttributeError(self.name)
        else:
            if self.fget is not None:
                rv = self.fget(obj, rv)
            return rv

    def __set__(self, obj, value):
        if self.read_only:
            raise AttributeError('read only property')
        
        if self.fset is not None:
            value = self.fset(obj, value)

        from .data import setitem
        setitem(self.flook(obj), self.name, value)

    def __delete__(self, obj):
        if self.read_only:
            raise AttributeError('read only property')
        
        from .data import delitem
        delitem(self.flook(obj), self.name)

        if self.fdel is not None:
            self.fdel(obj)

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self.name!r} from {self.src!r}>'
    
    def deleter(self, fdel):
        self.fdel = fdel
        return self

    def getter(self, fget):
        self.fget = fget
        return self

    def looker(self, source):
        self.src = source

        if source == 'self':
            self.flook = _selflookup
        elif callable(source):
            self.flook = source
        else:
            from .data import getitem

            def flook(obj):
                return getitem(obj, self.src)

            self.flook = flook

        return self
    
    def setter(self, fset):
        self.fset = fset
        return self


    

class dict_lookup_property(object):

    """Baseclass for `environ_property` and `header_property`."""
    read_only = False

    def __init__(self, name, default=None, lookup=None, load_func=None, dump_func=None,
                 read_only=None, doc=None):
        self.name = name
        self.default = default
        self.load_func = load_func
        self.dump_func = dump_func
        if lookup and isinstance(lookup, str):
            def attr_lookup(obj):
                return getattr(obj, attr_lookup.attr)
            attr_lookup.attr = lookup
            self.lookup_func = attr_lookup
        else:
            self.lookup_func = lookup

        if read_only is not None:
            self.read_only = read_only
        self.__doc__ = doc

    def lookup(self, obj):
        return self.lookup_func(obj)

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        storage = self.lookup(obj)
        if self.name not in storage:
            return self.default
        rv = storage[self.name]
        if self.load_func is not None:
            try:
                rv = self.load_func(rv)
            except (ValueError, TypeError):
                rv = self.default
        return rv

    def __set__(self, obj, value):
        if self.read_only:
            raise AttributeError('read only property')
        if self.dump_func is not None:
            value = self.dump_func(value)
        self.lookup(obj)[self.name] = value

    def __delete__(self, obj):
        if self.read_only:
            raise AttributeError('read only property')
        self.lookup(obj).pop(self.name, None)

    def __repr__(self):
        return '<%s %s>' % (
            self.__class__.__name__,
            self.name
        )


def deprecated(alt=None, version=None, *, message=None, onload=False, once=False):
    """Issues a deprecated warning on module load or when the decorated function is invoked.
    """
    def decorator(func: _T) -> _T:
        name = f'{func.__module__}.{func.__qualname__}()'
        altname = alt if alt is None or isinstance(alt, str)\
                    else f'{alt.__module__}.{alt.__qualname__}()'
        msg = (message or ''.join((
                '{name} is deprecated and will be removed in ',
                'version "{version}".' if version else 'upcoming versions.',
                ' Use {altname} instead.' if altname else '',
            ))).format(name=name, altname=altname, version=version)

        if onload:
            warn(msg, DeprecationWarning, 2)
        
        if isinstance(func, type):
            class wrapper(func):
                __slots__ = ()
                
                __wrapped__ = func

                def __new__(cls, *args, **kwds):
                    # if not hasattr(decorator, '_deprecated_warned'):
                    #     if once:
                    #         decorator._deprecated_warned = True
                    warn(f'{msg}', stacklevel=2)
                    return super().__new__(cls, *args, **kwds)

            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
        else:
            @wraps(func)
            def wrapper(*a, **kw):
                # if not hasattr(decorator, '_deprecated_warned'):
                #     if once:
                #         decorator._deprecated_warned = True
                warn(f'{msg}', stacklevel=2)
                return func(*a, **kw)

        return wrapper

    return decorator





def with_metaclass(meta, *bases, **ns):
    """Create a base class with a metaclass."""
    # This requires a bit of explanation: the basic idea is to make a dummy
    # metaclass for one level of class instantiation that replaces itself with
    # the actual metaclass.
    class metaclass(type):

        def __new__(cls, name, this_bases, d):
            if sys.version_info[:2] >= (3, 7):
                # This version introduced PEP 560 that requires a bit
                # of extra care (we mimic what is done by __build_class__).
                resolved_bases = types.resolve_bases(bases)
                if resolved_bases is not bases:
                    d['__orig_bases__'] = bases
            else:
                resolved_bases = bases
            return meta(name, resolved_bases, d)

        @classmethod
        def __prepare__(cls, name, this_bases):
            return meta.__prepare__(name, bases)
    return type.__new__(metaclass, 'temporary_class', (), {})

    # seen = {meta}
    # tbases = (t for b in bases if (t := b.__class__) in seen or seen.add(t))
    # class metaclass(meta, *tbases):

    #     def __new__(cls, name, this_bases, d):
    #         if sys.version_info[:2] >= (3, 7):
    #             # This version introduced PEP 560 that requires a bit
    #             # of extra care (we mimic what is done by __build_class__).
    #             resolved_bases = types.resolve_bases(bases)
    #             if resolved_bases is not bases:
    #                 d['__orig_bases__'] = bases
    #         else:
    #             resolved_bases = bases
    #         return super().__new__(cls, name, resolved_bases, d)

    #     @classmethod
    #     def __prepare__(cls, name, this_bases):
    #         return meta.__prepare__(name, bases)

    # return type.__new__(metaclass, 'temporary_class', (), {})


    # seen = {meta}
    # tbases = (t for b in bases if (t := b.__class__) in seen or seen.add(t))
    # class metaclass(meta, *tbases):
    #     pass

    # if not ns.get('__module__'):
    #     try:
    #         mod = sys._getframe(1).f_globals.get('__name__')
    #     except (AttributeError, ValueError):
    #         pass
    #     else:
    #         mod and ns.setdefault('__module__', mod)

    # return metaclass('temporary_class', bases, ns) 

    # class metaclass(type):
    #     def __new__(cls, name, this_bases, d):
    #         return meta(name, bases, d)

    # return type.__new__(metaclass, "temporary_class", (), ns)


def add_metaclass(metaclass):
    """Class decorator for creating a class with a metaclass."""
    def wrapper(cls):
        orig_vars = cls.__dict__.copy()
        slots = orig_vars.get('__slots__')
        if slots is not None:
            if isinstance(slots, str):
                slots = [slots]
            for slots_var in slots:
                orig_vars.pop(slots_var)
        orig_vars.pop('__dict__', None)
        orig_vars.pop('__weakref__', None)
        if hasattr(cls, '__qualname__'):
            orig_vars['__qualname__'] = cls.__qualname__
        return metaclass(cls.__name__, cls.__bases__, orig_vars)
    return wrapper



def calling_scope(depth=2, *, globals: bool=None, locals: bool=None):
    """Get the globals() or locals() scope of the calling scope"""
    if globals is locals is None:
        globals = True
    elif globals and locals or not (globals or locals):
            raise ValueError(f'args globals and locals are mutually exclusive')

    try:
        if globals:
            scope = sys._getframe(depth).f_globals
        else:
            scope = sys._getframe(depth).f_locals
    except (AttributeError, ValueError):
        raise
    else:
        return types.MappingProxyType(scope)