from abc import ABCMeta, abstractmethod
import typing as t 

from inspect import Parameter
from collections.abc import Mapping, Sequence, Set
from djx.common.collections import Arguments, frozendict

from djx.di import get_ioc_container
from djx.common.utils import export
from djx.di.common import Depends, Injectable
from djx.schemas.decorator import ParameterInfo



ioc = get_ioc_container()

T_Param = t.TypeVar('T_Param')
T_ParamData = t.Union[Mapping[str, T_Param], Set[T_Param], Sequence[T_Param], T_Param, t.Literal[Parameter.empty], None]

export('T_Param', 'T_ParamDataType')



T_ParamDataType = Injectable[T_ParamData]





@export()
class ParamData(t.Generic[T_Param]):
    
    __slots__ = ()

    @classmethod
    def register(cls, sub: type['ParamData']=...):
        if sub is ...:
            return cls.register
        else:
            return cls.register(sub)
    


@export()
@ioc.value(use=(), at='request', cache=True)
class PathArgs(Sequence[T_Param]):
    
    __slots__ = ()
    


@export()
@ioc.value(use=frozendict(), at='request', cache=True)
class PathKwargs(Mapping[str, T_Param]):
    
    __slots__ = ()
    
    


@export()
@ioc.injectable(at='request', cache=True)
class PathData(Arguments):
    """PathData ArgumentsObject"""

    __slots__ = ()

    def __new__(cls, args: Arguments):
        return super().__new__(cls, args, kwargs)

    def __getitem__(self, key: ParameterInfo):
        try:
            return self.kwargs[key]
        except KeyError:
            if key.kind != Parameter.KEYWORD_ONLY:
                if key.kind == Parameter.VAR_POSITIONAL:
                    return self.args[key.index:]
                elif len(self.args) > key.index:
                    return self.args[key.index]



@export()
@ioc.value(use=frozendict(), at='request', cache=True)
class QueryData(Mapping[str, T_Param]):
    """PathData ArgumentsObject"""

    __slots__ = ()



