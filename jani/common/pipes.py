
from collections import deque
import typing as t 


from collections.abc import Callable
from jani.common.collections import frozendict, Arguments

from jani.di import get_ioc_container, IocContainer


_T_Pipe = t.TypeVar('_T_Pipe', covariant=True)
_T_Return = t.TypeVar('_T_Return', covariant=True)


_empty_arguments = Arguments()

class Pipeline(t.Generic[_T_Pipe, _T_Return]):

    __slots__ = '_pipes', '_tap' '_arguments'

    _default_tap: t.ClassVar[t.Union[Callable[..., _T_Return], None]] = None
    
    _arguments: t.Final[Arguments]
    _pipes: t.Final[deque[tuple[_T_Pipe, Arguments]]]
    _tap: t.Final[t.Union[Callable[..., _T_Return], None]]

    def __init__(self, *pipes, tap: t.Union[Callable[..., _T_Return], None]=None, args=(), kwargs=frozendict()) -> None:
        self._arguments = _empty_arguments.merge(args, kwargs)
        self._pipes = deque()
        self._tap = tap or self._default_tap

    @property
    def pipes(self):
        return self._pipes
        
    @property
    def tap(self):
        return self._tap
        
    def append(self, pipe: t.Union[Callable[..., _T_Return], Pipe], *args, **kwargs):
        self._pipes.append()

    def _make_pipe(self, func: t.Union[Callable[..., _T_Return], Pipe], *args, **kwargs):
        if isinstance(func, Pipe):
            pass

    def __call__(self, *a, **kw) -> _T_Return:
        return self.run(*a, **kw) 
    
    def run(self, *a, **kw) -> _T_Return:
        arguments = self._arguments
        if a:
            arg_ = a[:1]
            a = a[1:]
        else:
            arg_ = ()

        if self._tap:
            tap = self._tap
            for pipe, arguments in self._pipes:
                if arguments:
                    arg_ = tap(pipe, *arg_, *arguments.args, *a, **arguments.kwargs.merge(kw)),
                else:
                    arg_ = tap(pipe, *arg_,  *a, **kw),
        else:
            for pipe, arguments in self._pipes:
                if arguments:
                    arg_ = pipe(arg_, *arguments.args, *a, **arguments.kwargs.merge(kw)),
                else:
                    arg_ = pipe(*arg_,  *a, **kw),

        if arg_:
            return arg_[0]



@export()
class TappedPipeline(Pipeline):
    """TappedPipeline PipelineObject"""

    def pipe(self, v, /,  *a, **kw) -> _T_Return:
        arguments = self._arguments
        
        tap = self._tap
        for pipe, arguments in self._pipes:
            if arguments:
                v = tap(pipe, v, *a, *arguments.args, **arguments.kwargs.merge(kw))
            else:
                v = tap(pipe, v,  *a, **kw)
        return v



@export()
class PurePipeline(Pipeline):
    """TappedPipeline PipelineObject"""


    def pipe(self, v, /,  *a, **kw) -> _T_Return:
        arguments = self._arguments
        for pipe, arguments in self._pipes:
            if arguments:
                v = pipe(v, *a, *arguments.args, **arguments.kwargs.merge(kw))
            else:
                v = pipe(v,  *a, **kw)
        return v



# class Pipe(Callable[..., _T_Co]):

#     __slots__ = '_func', '_arguments',

#     func: Callable[..., _T_Return]
#     _arguments: t.Final[Arguments]

#     def __new__(cls, func, args: t.Union[tuple, Arguments] =(), kwargs: dict[str, t.Any]=frozendict(), /) -> 'Pipe[_T_Return]':
        
#         if func.__class__ is cls:
#             pass
        
#         self = object.__new__(cls)
#         self._func = func
#         self._arguments = args
#         self._arguments.replace()

#     if t.TYPE_CHECKING:

#         def __init__(self, func: Callable[..., _T_Return], args: t.Union[tuple, Arguments] =(), kwargs: dict[str, t.Any]=frozendict(), /) -> 'Pipe[_T_Return]':
#             args_ = Arguments().extend(args, kwargs)

#             self._func = func
#             self._arguments = args
    
#     @property
#     def arguments(self):
#         return self._arguments

#     @property
#     def func(self):
#         return self._func

#     def __eq__(self, x):
#         if isinstance(x, Pipe):
#             return self.func == x.func and self.arguments == x.arguments
#         return NotImplemented
    
#     def __hash__(self, ):
#         if isinstance(x, Pipe):
#             return self.func == x.func and self.arguments == x.arguments
#         return NotImplemented
        

