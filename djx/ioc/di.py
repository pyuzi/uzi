from typing import (
    TypeVar,
    Union
)
from contextvars import ContextVar
from contextlib import contextmanager


from flex.utils.decorators import export
from flex.utils.proxy import Proxy

from .abc import Injectable, Injector

__all__ = [
    'injector'
]



_I = TypeVar('_I', bound=Injector)

InjectorStack = tuple[_I]


__ctx_stack_var: ContextVar[InjectorStack[_I]] = ContextVar('__ctx_stack_var', default=())



@export
def get_current_injector(*a) -> Injector:
    return get_current_stack((None,))[-1]


def get_current_stack(default=()) -> InjectorStack[_I]:
    return __ctx_stack_var.get(None) or default


injector = Proxy(get_current_injector)




@export()
@contextmanager
def use_context(*ctx):
    

    
    print(f'+++ switch sites {token.old_value} -->', get_all_current_site_pks())

    try:
        yield get_current_site()
        print(f' - start using site -->', get_all_current_site_pks(), '-->', get_current_site())
    finally:
        print(f' - end using site   -->', s := get_all_current_site_pks())
        _site_pk_ctx_var.reset(token)

    print(f'--- reset sites {s} ---> {token.old_value}')



