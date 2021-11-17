import typing as t 
import operator as op

from functools import cache, reduce

from djx.common.utils import export
from djx.common.enum import StrEnum, IntFlag, auto


from . import abc



@export()
class ParamSource(StrEnum, fields='dep,_list,_map'):
    
    args: 'ParamSource'       = auto(), abc.Args
    kwargs: 'ParamSource'     = auto(), abc.Kwargs
    path: 'ParamSource'       = auto(), abc.PathParams,
    
    query: 'ParamSource'      = auto(), abc.Query,
    body: 'ParamSource'       = auto(), abc.Body,
    header: 'ParamSource'     = auto(), abc.Headers,

    form: 'ParamSource'       = auto(), abc.Form,
    file: 'ParamSource'       = auto(), abc.Files,

    cookie: 'ParamSource'     = auto(), abc.Cookies, 

    params: 'ParamSource'     = auto(), abc.Params, 
    input: 'ParamSource'      = auto(), abc.Input, 


vardump(ParamSource.__members__)


@export()
class ParamFlag(IntFlag, fields='src'):
    
    injectable: 'ParamFlag'      = auto()
    sequence: 'ParamFlag'        = auto()
    mapping: 'ParamFlag'         = auto()

    builtin: 'ParamFlag'         = auto()
    validates: 'ParamFlag'       = auto()
    
    static: 'ParamFlag'          = auto()
    dymnamic: 'ParamFlag'        = auto()

