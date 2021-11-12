
import typing as t 

from functools import partial

from djx.common import typing as tt
from djx.common.utils import export




@export()
def get_args(tp):
    return tt.get_args(tp)


@export()
def get_origin(obj):
    return tt.get_origin(obj)


@export()
def get_all_type_hints(obj: t.Any, globalns: t.Any = None, localns: t.Any = None) -> t.Any:
    return tt.get_all_type_hints(obj, globalns=globalns, localns=localns)

