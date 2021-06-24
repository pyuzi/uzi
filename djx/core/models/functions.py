import typing as t

from collections.abc import Callable

from django.db.models import Field
from django.db.models.functions import JSONObject as BaseJSONObject


from djx.common.utils import export


from .fields.json import JSONObjectField, _T_JSONObject, _T_ObjectFactory



@export()
class JSONObject(BaseJSONObject, t.Generic[_T_JSONObject]):

    output_field = JSONObjectField[_T_JSONObject]()
    
    @t.overload
    def __init__(self, type: type[_T_JSONObject]=..., /, **fields):
        ...
    @t.overload
    def __init__(self, type: type[_T_JSONObject]=..., factory: _T_ObjectFactory=..., /, **fields):
        ...
    @t.overload
    def __init__(self, factory: _T_ObjectFactory=..., /, **fields):
        ...
    @t.overload
    def __init__(self, output_field: Field=..., /, **fields):
        ...
    def __init__(self, output: t.Any=..., factory: _T_ObjectFactory=..., /, **fields):
        super().__init__(**fields)
        if output is ...:
            return
        elif factory is not ...:
            self.output_field = JSONObjectField(type=output, factory=factory)
        elif isinstance(output, Field):
            self.output_field = output
        elif isinstance(output, type):
            self.output_field = JSONObjectField(type=output)
        else:
            self.output_field = JSONObjectField(factory=output)
