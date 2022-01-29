from contextvars import ContextVar
import typing as t 


from laza.common.functools import export

if t.TYPE_CHECKING:
    from .new_injectors import Injector



@export
class Kernel:

    _ctx: ContextVar['Injector']

    def __init__(self, ctx: ContextVar['Injector']=None) -> None:
        self._ctx = ctx or ContextVar('Injector', default=None)
        self.current = self._ctx.get
    
    def current(self):
        return self._ctx.get()
    
    def set():
        pass




