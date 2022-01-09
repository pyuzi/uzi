import typing as t 
import operator as op

from functools import cache, reduce
from collections.abc import Callable, Hashable, Mapping

from jani.common.functools import export
from jani.common.enum import StrEnum, IntFlag, auto


from . import abc, Request
from .types import HttpMethod

if t.TYPE_CHECKING:
    from .config import ViewConfig, ActionConfig
    from .views import View


def http_method_action_resolver(config: 'ViewConfig', actions: Mapping[Hashable, 'ActionConfig']) -> Callable[['View', Request], 'ActionConfig']:
    if not actions:
        raise TypeError(f'No available actions for {config.target.__name__}')
    
    # vardump(
    #     __view__=config.target,
    #     __http_methods__=config.http_methods, 
    #     allowed_http_methods=config.http_method_names
    # )


    for verb, act in actions.items():
        # vardump(
        #     __action__=act.name,
        #     __http_verbs__=act.http_methods, 
        #     allowed_http_methods=act.http_method_names
        # )
        if verb not in act.http_methods:
            raise TypeError(f'http method {verb!r} not allowed for action {act!r}')

    # if 'get' in actions and 'head' not in actions:
    #     actions['head'] = actions['get']

    def resolver(view: 'View', req: Request):
        nonlocal actions
        try:
            return actions[req.method.lower()]
        except KeyError:
            view.abort(405)
    
    return resolver
        




@export()
class ParamSource(StrEnum, fields='dep,_list,_map'):
    
    args: 'ParamSource'       = auto(), abc.Args
    kwargs: 'ParamSource'     = auto(), abc.Kwargs
    path: 'ParamSource'       = auto(), abc.Arguments,
    
    query: 'ParamSource'      = auto(), abc.Query,
    body: 'ParamSource'       = auto(), abc.Body,
    header: 'ParamSource'     = auto(), abc.Headers,

    form: 'ParamSource'       = auto(), abc.Form,
    file: 'ParamSource'       = auto(), abc.Files,

    cookie: 'ParamSource'     = auto(), abc.Cookies, 

    params: 'ParamSource'     = auto(), abc.Params, 
    input: 'ParamSource'      = auto(), abc.Inputs, 



@export()
class ParamFlag(StrEnum, fields='src'):
    
    injectable: 'ParamFlag'      = auto()
    sequence: 'ParamFlag'        = auto()
    mapping: 'ParamFlag'         = auto()

    builtin: 'ParamFlag'         = auto()
    validates: 'ParamFlag'       = auto()
    
    static: 'ParamFlag'          = auto()
    dymnamic: 'ParamFlag'        = auto()


