import typing as t 
import operator as op

from functools import cache, reduce

from djx.common.utils import export
from djx.common.enum import StrEnum, IntFlag, auto



@export()
class ParamType(IntFlag):
    path: 'ParamType'       = auto()
    query: 'ParamType'      = auto()
    header: 'ParamType'     = auto()
    body: 'ParamType'       = auto()
    form: 'ParamType'       = auto()
    file: 'ParamType'       = auto()
    cookie: 'ParamType'     = auto()


    @classmethod
    @cache
    def any(cls) -> 'ParamType':
        return reduce(op.or_, cls)
