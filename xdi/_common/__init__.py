
import inspect
import sys
import types
import typing as t
from collections import ChainMap
from collections.abc import Callable
from importlib import import_module
from typing import ForwardRef


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




def typed_signature(
    callable: Callable[..., t.Any], *, follow_wrapped=True, globalns=None, localns=None
) -> inspect.Signature:
    sig = inspect.signature(callable, follow_wrapped=follow_wrapped)

    if follow_wrapped:
        callable = inspect.unwrap(
            callable, stop=(lambda f: hasattr(f, "__signature__"))
        )

    if globalns is None:
        globalns = getattr(callable, "__globals__", None) or getattr(
            import_module(callable.__module__), "__dict__", None
        )

    params = (
        p.replace(annotation=eval_type(p.annotation, globalns, localns))
        for p in sig.parameters.values()
    )

    return sig.replace(
        parameters=params,
        return_annotation=eval_type(sig.return_annotation, globalns, localns),
    )


def eval_type(value, globalns, localns=None):

    if isinstance(value, str):
        value = ForwardRef(value)
    try:
        return t._eval_type(value, globalns, localns)
    except NameError:
        # this is ok, it can be fixed with update_forward_refs
        return value




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


