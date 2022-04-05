
import inspect
import sys
import typing as t 
from collections.abc import Callable

from typing import get_args, get_origin, ForwardRef

from typing_extensions import Self

if sys.version_info < (3, 10): # pragma: py-gt-39
    UnionType = type(t.Union[t.Any, None]) 
else: # pragma: py-lt-310
    from types import UnionType 




def typed_signature(callable: Callable[..., t.Any], *, follow_wrapped=True, globalns=None, localns=None) -> inspect.Signature:
    sig = inspect.signature(callable, follow_wrapped=follow_wrapped)

    if follow_wrapped:
        callable = inspect.unwrap(callable, stop=(lambda f: hasattr(f, "__signature__")))
    
    if globalns is None:
        from xdi._common.imports import ImportRef
            
        globalns = getattr(callable, '__globals__', None) \
            or getattr(ImportRef(callable).module(None), '__dict__', None)

    params = (
            p.replace(annotation=eval_type(p.annotation, globalns, localns)) 
                for p in sig.parameters.values()
        )
    
    return sig.replace(
            parameters=params, 
            return_annotation=eval_type(sig.return_annotation, globalns, localns)
        )


def eval_type(value, globalns, localns=None):

    if isinstance(value, str):
        if sys.version_info >= (3, 7):
            value = ForwardRef(value, is_argument=False)
        else:
            value = ForwardRef(value)
    try:
        return t._eval_type(value, globalns, localns)
    except NameError:
        # this is ok, it can be fixed with update_forward_refs
        return value        
