from __future__ import annotations
import copy
import math
import operator
import typing as t
from functools import cache, partial



_TP = t.TypeVar('_TP', covariant=True)
_T_Fget = t.Callable[[], _TP]


_notset = object()



def isproxy(obj, cls: t.Union[type[Proxy], tuple[type[Proxy]]] = None) -> bool:
    return isproxytype(type(obj), cls) or \
        (isproxytype(obj, cls) if cls is not None and isinstance(obj, ProxyType) else False)




@cache
def isproxytype(typ: type[t.Any], cls: t.Union[type[Proxy], tuple[type[Proxy]]] = None) -> bool:
    return issubclass(typ, cls or (Proxy, ProxyType))


_set_own_attr = object.__setattr__
_notset_ref = lambda: None


class _ProxyLookup(t.Generic[_TP]):
    """Descriptor that handles proxied attribute lookup for
    :class:`LocalProxy`.

    :param f: The built-in function this attribute is accessed through.
        Instead of looking up the special method, the function call
        is redone on the object.
    :param fallback: Call this method if the proxy is unbound instead of
        raising a :exc:`RuntimeError`.
    :param class_value: Value to return when accessed from the class.
        Used for ``__doc__`` so building docs still works.
    """

    __slots__ = ("bind_f", "fallback", "class_value", "name")
    


    def __init__(self, f=None, fallback=None, class_value=None):
        if hasattr(f, "__get__"):
            # A Python function, can be turned into a bound method.

            def bind_f(obj):
                return f.__get__(obj, type(obj))

        elif f is not None:
            # A C function, use partial to bind the first argument.

            def bind_f(obj):
                return partial(f, obj)

        else:
            # Use getattr, which will produce a bound method.
            bind_f = None

        self.bind_f = bind_f
        self.fallback = fallback
        self.class_value = class_value

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance: Proxy[_TP], owner=None):
        if instance is None:
            if self.class_value is not None:
                return self.class_value

            return self
    
        obj: _TP = instance.__proxy_target__
        # if obj is NotImplemented:
        #     if self.fallback:
        if self.bind_f is not None:
            return self.bind_f(obj)

        return getattr(obj, self.name)

    def __repr__(self):
        return f"proxy {self.name}"

    def __call__(self, instance, *args, **kwargs):
        """Support calling unbound methods from the class. For example,
        this happens with ``copy.copy``, which does
        ``type(x).__copy__(x)``. ``type(x)`` can't be proxied, so it
        returns the proxy type and descriptor.
        """
        return self.__get__(instance, type(instance))(*args, **kwargs)


class _ProxyIOp(_ProxyLookup):
    """Look up an augmented assignment method on a proxied object. The
    method is wrapped to return the proxy instead of the object.
    """

    __slots__ = ()

    def __init__(self, f=None, fallback=None):
        super().__init__(f, fallback)

        def bind_f(instance, obj):
            def i_op(self, other):
                f(self, other)
                return instance

            return i_op.__get__(obj, type(obj))

        self.bind_f = bind_f


def _l_to_r_op(op):
    """Swap the argument order to turn an l-op into an r-op."""

    def r_op(obj, other):
        return op(other, obj)

    return r_op


class ProxyType(type):
    pass


_proxy_attrs = frozenset((
    '__proxy_func__',  
    '__proxy_target_val__', 
    '__proxy_target__',
    # '__call__',
    # '__iadd__',
    # '__isub__',
    # '__imul__ ',
    # '__imatmul__ ',
    # '__itruediv__ ',
    # '__ifloordiv__ ',
    # '__imod__ ',
    # '__ipow__ ',
    # '__ilshift__ ',
    # '__irshift__ ',
    # '__iand__ ',
    # '__ixor__ ',
    # '__ior__ ',
))



class Proxy(t.Generic[_TP], metaclass=ProxyType):
    """Forwards all operations to the return value of the given callable `fget`.

    ``__repr__`` and ``__class__`` are forwarded, so ``repr(x)`` and
    ``isinstance(x, cls)`` will look like the proxied object. Use
    ``issubclass(type(x), Proxy)`` to check if an object is a
    proxy.
    """

    __slots__ = (
        '__proxy_func__',  
        '__proxy_target_val__', 
        '__weakref__',
    )

    __proxy_func__: _T_Fget[_TP]
    

    @t.overload
    def __new__(cls, fget: _T_Fget[_TP], /, *, cache: bool=None, weak: bool=None, callable: bool=None, **kwds) -> _TP: 
        ...
    @t.overload
    def __new__(cls, *, cache: bool=None, weak: bool=None, callable: bool=None, **kwds) -> t.Callable[[_T_Fget[_TP]], _TP]: 
        ...
    def __new__(cls, fget: _T_Fget[_TP]=..., /, *, cache: bool=None, weak: bool=None, callable: bool=None, **kwds) -> _TP:
        if cls is Proxy:
            if not(cache is callable is weak is None):
                if weak is True and cache is not True:
                    raise ValueError(f'Weak proxy must be cached `cache=True`')

                cls = WeakCallableProxy if True is cache is callable is weak \
                    else CachedCallableProxy if True is cache is callable \
                        else WeakProxy if True is cache is weak \
                            else CachedProxy if cache is True \
                                else CallableProxy if callable is True\
                                    else SimpleProxy
        if fget is ...:
            def decorate(fget):
                return cls(fget)
            return decorate
        elif isproxytype(type(fget)):
            rv = cls._clone_proxy_from(fget, cache=cache, weak=weak, callable=callable, **kwds)
            if rv is NotImplemented:
                raise TypeError(f'cannot create a {cls.__name__} from {type(fget).__name__}.')
            return rv
        else:
            return super().__new__(cls)

    def __init__(self, fget: _T_Fget[_TP], /, *, cached: bool=None, weak: bool=None, callable: bool=None) -> None:
        _set_own_attr(self, '__proxy_func__', fget)

    @classmethod
    def _clone_proxy_from(cls, obj, **kwds):
        if isproxytype(type(obj), cls):
            return obj
        return NotImplemented  

    @classmethod
    def __proxy_class__(cls):
        return cls

    @property
    def __proxy_target__(self) -> _TP:
        """Return the current object.  This is useful if you want the real
        object behind the proxy at a time for performance reasons or because
        you want to pass the object into a different context.
        """
        return self.__proxy_func__()

#
    __doc__ = _ProxyLookup(  # type: ignore
        class_value=__doc__, fallback=lambda self: type(self).__doc__
    )
    # __del__ should only delete the proxy

    def __repr__(self):
        return f'{type(self).__name__}({self.__proxy_target__})'

    # def __getattribute__(self, name):
    #     if name in _proxy_attrs:
    #         return super().__getattribute__(name)
    #     return getattr(super().__getattribute__('__proxy_target__'), name)

    def __getattr__(self, name):
        if name in _proxy_attrs:
            raise AttributeError(name)
        
        return getattr(self.__proxy_target__, name)

    __str__ = _ProxyLookup(str)
    __bytes__ = _ProxyLookup(bytes)
    __format__ = _ProxyLookup()  # type: ignore
    __lt__ = _ProxyLookup(operator.lt)
    __le__ = _ProxyLookup(operator.le)
    __eq__ = _ProxyLookup(operator.eq)
    __ne__ = _ProxyLookup(operator.ne)
    __gt__ = _ProxyLookup(operator.gt)
    __ge__ = _ProxyLookup(operator.ge)
    __hash__ = _ProxyLookup(hash)  # type: ignore
    __bool__ = _ProxyLookup(bool, fallback=lambda self: False)
    # __getattr__ = _ProxyLookup(getattr)
    # __getattribute__ triggered through __getattr__
    __setattr__ = _ProxyLookup(setattr)
    __delattr__ = _ProxyLookup(delattr)
    __dir__ = _ProxyLookup(dir, fallback=lambda self: [])  # type: ignore
    # __get__ (proxying descriptor not supported)
    # __set__ (descriptor)
    # __delete__ (descriptor)
    # __set_name__ (descriptor)
    # __objclass__ (descriptor)
    # __slots__ used by proxy itself
    # __dict__ (__getattr__)
    # __weakref__ used by proxy itself
    # __init_subclass__ (proxying metaclass not supported)
    # __prepare__ (metaclass)
    __class__ = _ProxyLookup(fallback=lambda self: type(self))  # type: ignore
    __instancecheck__ = _ProxyLookup(lambda self, other: isinstance(other, self))
    __subclasscheck__ = _ProxyLookup(lambda self, other: issubclass(other, self))
    # __class_getitem__ triggered through __getitem__
    __call__ = _ProxyLookup(lambda self, *args, **kwargs: self(*args, **kwargs))
    __len__ = _ProxyLookup(len)
    __length_hint__ = _ProxyLookup(operator.length_hint)
    __getitem__ = _ProxyLookup(operator.getitem)
    __setitem__ = _ProxyLookup(operator.setitem)
    __delitem__ = _ProxyLookup(operator.delitem)
    # __missing__ triggered through __getitem__
    __iter__ = _ProxyLookup(iter)
    __next__ = _ProxyLookup(next)
    __reversed__ = _ProxyLookup(reversed)
    __contains__ = _ProxyLookup(operator.contains)
    __add__ = _ProxyLookup(operator.add)
    __sub__ = _ProxyLookup(operator.sub)
    __mul__ = _ProxyLookup(operator.mul)
    __matmul__ = _ProxyLookup(operator.matmul)
    __truediv__ = _ProxyLookup(operator.truediv)
    __floordiv__ = _ProxyLookup(operator.floordiv)
    __mod__ = _ProxyLookup(operator.mod)
    __divmod__ = _ProxyLookup(divmod)
    __pow__ = _ProxyLookup(pow)
    __lshift__ = _ProxyLookup(operator.lshift)
    __rshift__ = _ProxyLookup(operator.rshift)
    __and__ = _ProxyLookup(operator.and_)
    __xor__ = _ProxyLookup(operator.xor)
    __or__ = _ProxyLookup(operator.or_)
    __radd__ = _ProxyLookup(_l_to_r_op(operator.add))
    __rsub__ = _ProxyLookup(_l_to_r_op(operator.sub))
    __rmul__ = _ProxyLookup(_l_to_r_op(operator.mul))
    __rmatmul__ = _ProxyLookup(_l_to_r_op(operator.matmul))
    __rtruediv__ = _ProxyLookup(_l_to_r_op(operator.truediv))
    __rfloordiv__ = _ProxyLookup(_l_to_r_op(operator.floordiv))
    __rmod__ = _ProxyLookup(_l_to_r_op(operator.mod))
    __rdivmod__ = _ProxyLookup(_l_to_r_op(divmod))
    __rpow__ = _ProxyLookup(_l_to_r_op(pow))
    __rlshift__ = _ProxyLookup(_l_to_r_op(operator.lshift))
    __rrshift__ = _ProxyLookup(_l_to_r_op(operator.rshift))
    __rand__ = _ProxyLookup(_l_to_r_op(operator.and_))
    __rxor__ = _ProxyLookup(_l_to_r_op(operator.xor))
    __ror__ = _ProxyLookup(_l_to_r_op(operator.or_))
    __iadd__ = _ProxyIOp(operator.iadd)
    __isub__ = _ProxyIOp(operator.isub)
    __imul__ = _ProxyIOp(operator.imul)
    __imatmul__ = _ProxyIOp(operator.imatmul)
    __itruediv__ = _ProxyIOp(operator.itruediv)
    __ifloordiv__ = _ProxyIOp(operator.ifloordiv)
    __imod__ = _ProxyIOp(operator.imod)
    __ipow__ = _ProxyIOp(operator.ipow)
    __ilshift__ = _ProxyIOp(operator.ilshift)
    __irshift__ = _ProxyIOp(operator.irshift)
    __iand__ = _ProxyIOp(operator.iand)
    __ixor__ = _ProxyIOp(operator.ixor)
    __ior__ = _ProxyIOp(operator.ior)
    __neg__ = _ProxyLookup(operator.neg)
    __pos__ = _ProxyLookup(operator.pos)
    __abs__ = _ProxyLookup(abs)
    __invert__ = _ProxyLookup(operator.invert)
    __complex__ = _ProxyLookup(complex)
    __int__ = _ProxyLookup(int)
    __float__ = _ProxyLookup(float)
    __index__ = _ProxyLookup(operator.index)
    __round__ = _ProxyLookup(round)
    __trunc__ = _ProxyLookup(math.trunc)
    __floor__ = _ProxyLookup(math.floor)
    __ceil__ = _ProxyLookup(math.ceil)
    __enter__ = _ProxyLookup()
    __exit__ = _ProxyLookup()
    __await__ = _ProxyLookup()
    __aiter__ = _ProxyLookup()
    __anext__ = _ProxyLookup()
    __aenter__ = _ProxyLookup()
    __aexit__ = _ProxyLookup()
    __copy__ = _ProxyLookup(copy.copy)
    __deepcopy__ = _ProxyLookup(copy.deepcopy)
    # __getnewargs_ex__ (pickle through proxy not supported)
    # __getnewargs__ (pickle)
    # __getstate__ (pickle)
    # __setstate__ (pickle)
    # __reduce__ (pickle)
    # __reduce_ex__ (pickle)
###


class SimpleProxy(Proxy[_TP]):

    __slots__ = ()

    __proxy_target_val__: _TP




class CachedProxy(Proxy[_TP]):

    __slots__ = ()

    __proxy_target_val__: _TP

    def __init__(self, fget: _T_Fget[_TP], /, **kwds) -> None:
        _set_own_attr(self, '__proxy_target_val__', _notset)
        _set_own_attr(self, '__proxy_func__', fget)

    @property
    def __proxy_target__(self) -> _TP:
        """Return the current object.  This is useful if you want the real
        object behind the proxy at a time for performance reasons or because
        you want to pass the object into a different context.
        """
        if self.__proxy_target_val__ is _notset:
            _set_own_attr(self, '__proxy_target_val__', self.__proxy_func__())

        return self.__proxy_target_val__



class WeakProxy(CachedProxy[_TP]):

    __slots__ = ()

    __proxy_target_val__: _TP

    def __init__(self, fget: _T_Fget[_TP], /, **kwds) -> None:
        _set_own_attr(self, '__proxy_target_val__', _notset_ref)
        _set_own_attr(self, '__proxy_func__', fget)

    @property
    def __proxy_target__(self) -> _TP:
        """Return the current object.  This is useful if you want the real
        object behind the proxy at a time for performance reasons or because
        you want to pass the object into a different context.
        """
        rv = self.__proxy_target_val__()
        if rv is None:
            _set_own_attr(self, '__proxy_target_val__', saferef(self.__proxy_func__()))
            return self.__proxy_target_val__()
    
        return rv








class ValueProxy(Proxy[_TP]):

    __slots__ = '__proxy_target__',

    def __init__(self, value: _TP, /, **kwds) -> None:
        _set_own_attr(self, '__proxy_target__', value)

    @property
    def __proxy_func__(self):
        val = self.__proxy_target__
        return lambda: val




class CallableProxy(Proxy[_TP]):

    __slots__ = ()

    def __call__(self) -> _TP:
        return self.__proxy_target__


class CallableValueProxy(ValueProxy[_TP], CallableProxy[_TP]):

    __slots__ = ()




class CachedCallableProxy(CachedProxy[_TP], CallableProxy[_TP]):

    __slots__ = ()



class WeakCallableProxy(WeakProxy[_TP], CallableProxy[_TP]):

    __slots__ = ()





def unproxy(val: t.Union[Proxy[_TP], _TP]) -> _TP:
    return getattr(val, '__proxy_target__', val)


if t.TYPE_CHECKING:
    _Proxy = Proxy
    
    @t.overload
    def proxy(fget: _T_Fget[_TP]) -> _TP: 
        ...
    @t.overload
    def proxy(fget: _T_Fget[_TP], /, *, cache: False = None, callable: False = None) -> _TP: ...
    @t.overload
    def proxy(fget: _T_Fget[_TP], /, *, cache: True, weak: False = None, callable: False = None) -> _TP: ...
    @t.overload
    def proxy(fget: _T_Fget[_TP], /, *, cache: True, weak: True, callable: False = None) -> _TP: ...
    @t.overload
    def proxy(fget: _T_Fget[_TP], /, *, callable: True, cache: False = None) -> t.Union[_TP, _T_Fget[_TP]]: ...
    @t.overload
    def proxy(fget: _T_Fget[_TP], /, *, cache: True, callable: True) -> t.Union[_TP, _T_Fget[_TP]]: ...
    @t.overload
    def proxy(fget: _T_Fget[_TP], /, *, cache: True, weak: True, callable: True) -> t.Union[_TP, _T_Fget[_TP]]:
        ...
    def proxy(fget: _T_Fget[_TP], /, *, cache: bool=False, callable: bool=False) -> _TP:
        ...

    Proxy = proxy

else:
    
    proxy = Proxy


from .saferef import saferef
