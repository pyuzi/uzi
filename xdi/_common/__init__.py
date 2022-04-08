
import sys
import types


import typing as t
from collections import ChainMap




def calling_frame(depth=1, *, globals: bool=None, locals: bool=None, chain: bool=None):
    """Get the globals() or locals() scope of the calling scope"""

    if None is globals is locals is chain:
        globals = True
    elif (not chain and True is globals is locals) or (False is globals is locals):
        raise ValueError(f'args `globals` and `locals` are mutually exclusive') # pragma: no cover

    try:
        frame = sys._getframe(depth + 1)
        if chain:
            scope = ChainMap(frame.f_locals, frame.f_globals)
        if globals:
            scope = frame.f_globals
        else:
            scope = frame.f_locals
    finally:
        return types.MappingProxyType(scope)




class MissingType:

    __slots__ = ()

    __value__: t.ClassVar['MissingType'] = None

    def __new__(cls):
        return cls.__value__

    @classmethod
    def _makenew__(cls, name):
        if cls.__value__ is None:
            cls.__value__ = object.__new__(cls)
        return cls()

    def __bool__(self): return False

    def __str__(self): return ''

    def __repr__(self): return f'Missing'

    def __reduce__(self):
        return self.__class__, () # pragma: no cover
    
    def __eq__(self, x):
        return x is self

    def __hash__(self):
        return id(self)







Missing = MissingType._makenew__('Missing')


