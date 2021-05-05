from __future__ import annotations

import typing as t
from collections.abc import Mapping, Iterable
from django.db.models.base import Model
from djx.common import json
from djx.common.collections import OrderedSet
import pydantic
from pydantic import (
    ValidationError, Field, Extra,
    validator, root_validator,
    fields, generics, BaseConfig, 
    EmailStr, FilePath, DirectoryPath, NameEmail,
    Json,
)
from pydantic.color import Color
from pydantic.utils import GetterDict
from djantic.main import ModelSchema 
from djx.common.utils import export

from django.db import models

__all__ = [
    'ValidationError', 
    'Extra',
    'Field',
    'validator',
    'EmailStr', 
    'FilePath', 
    'DirectoryPath', 
    'NameEmail', 
    'Json', 
    'Color',
    'root_validator',
]


T_Schema = t.TypeVar('T_Schema', bound='Schema')



class _ABcModel(models.Model):

    class Meta:
        abstract = True



@export()
class Schema(pydantic.BaseModel):
   
    class Config:
        json_loads = json.loads
        json_dumps = json.dumps

   


@export()
class GenericSchema(Schema, generics.GenericModel):
    pass



# Since "Model" word would be very confusing when used in django context
# this module basically makes alias for it named "Schema"
# and ads extra whistles to be able to work with django querysets and managers


class ModelGetter(GetterDict):
    def get(self, key: t.Any, default: t.Any = None) -> t.Any:
        result = super().get(key, default)

        if isinstance(result, models.Manager):
            return list(result.all())

        elif isinstance(result, models.QuerySet):
            return list(result)

        elif isinstance(result, models.FieldFile):
            if not result:
                return None
            return result.url

        return result



@export()
class ModelSchema(Schema, ModelSchema):

    class Config:
        orm_mode = True
        model = _ABcModel
        # getter_dict = ModelGetter




@export()
class GenericModelSchema(ModelSchema, GenericSchema):

    class Config:
        orm_mode = True
        # getter_dict = ModelGetter







@export()
def create_schema(
    __name__: str, 
    __bases__: t.Union[type[Schema], Iterable[type[Schema]]] = None, 
    *,
    __module__: str = None,
    __config__: type[BaseConfig] = None,
    __validators__: dict[str, classmethod] = None,
    **field_definitions: t.Any,
) -> type[T_Schema]:
    """Dynamically create a schema model.
    """
    args = locals()
    field_definitions.update((
        (k, args[k]) 
        for k in ('__config__', '__validators__')
        if args[k] is not None
    ))

    if not(__bases__ is None or isinstance(__bases__, type)):
        defs = OrderedSet(__bases__)
        bases = _schema_def_mro(defs)
        basename = f'_abc_{__name__}'
        __bases__ = type(basename, bases, {
            k : args[k] 
            for k in ('__module__',)
            if args[k] is not None
        })
    
    return pydantic.create_model(
                __name__, 
                __base__= __bases__ or Schema,
                __module__=__module__,
                **field_definitions
            )



def _schema_def_mro(defs) -> tuple:
    return tuple(_iter_bases_from_defs(defs))[::-1]


def _iter_bases_from_defs(defs: t.Dict, klasses=None, *, _skip=None) -> t.Generator[t.Type[T_Schema]]:
    _skip is None and (_skip := set())
    
    assert isinstance(defs, t.Mapping), (
        f'expected a Mapping[Type[Schema], Optional[Iterable[Schema]]]. Got {type(defs)}'
    )
    
    is_def = lambda o: o in defs
    def_bases = lambda o: filter(is_def, reversed(o.__mro__))

    for kls in (defs if klasses is None else klasses):
        if kls not in _skip:
            _skip.add(kls)

            extends = defs[kls]

            yield from _iter_bases_from_defs(defs, def_bases(kls), _skip=_skip)

            if extends:
                yield from _iter_bases_from_defs(defs, extends, _skip=_skip)

            yield kls
