import logging
import typing as t 
from django.db import models 
from enum import Enum as BaseEnum, IntFlag as BaseIntFlag


from jani.common.functools import export
from jani.common.enum import EnumMeta



logger = logging.getLogger(__name__)

def _enum_choices(enum):
    if isinstance(enum, EnumMeta):
        return enum._choices_()
    elif issubclass(enum, BaseEnum):
        return tuple((m._value_, m.name) for m in enum)
    else: 
        return None

    

class EnumFieldMixin:
    """EnumField object."""

    description = "A %(enum)s member"
    _base_enum_type = BaseEnum
    
    def __init__(self, *args, enum=None, **kwargs):
        if enum is None or not issubclass(enum, self._base_enum_type):
            raise TypeError(
                '%s enum must be a subclass of %s. %s given.'\
                % (self.__class__.__name__, self._base_enum_type, type(enum),)
            )

        self._enum_choices = _enum_choices(enum)
        kwargs.setdefault('choices', self._enum_choices)
        super().__init__(*args, **kwargs)

        self.enum = enum

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if kwargs.get('choices') == self._enum_choices:
            del kwargs['choices']
            
        kwargs['enum'] = self.enum

        return name, path, args, kwargs

    def to_python(self, value):
        return value if value is None else self.enum(value)

    def from_db_value(self, value, expression, connection, context=None):
        return value if value is None else self.enum(value)

    # def get_prep_value(self, value):
    #     return value if value is None else self.to_python(value).value


@export()
class StrEnumField(EnumFieldMixin, models.CharField):
    """EnumField object."""

    def __init__(self, *args, enum=None, **kwargs):
        kwargs.setdefault('max_length', 64)
        super().__init__(*args, enum=enum, **kwargs)






@export()
class IntEnumField(EnumFieldMixin, models.IntegerField):
    """IntEnumField object."""
    pass





@export()
class IntFlagField(IntEnumField):
    """IntFlagField object."""
    _base_enum_type = BaseIntFlag





# @export()
# class IntFlagField(models.IntegerField):
#     """IntEnumField object."""

#     # def get_lookup(self, lookup_name):
#     #     if lookup_name == 'exact':
#     #         lookup_name = 'band'
#     #     elif lookup_name == 'eq':
#     #         lookup_name = 'exact'

#     #     return super().get_lookup(lookup_name)


# @export()
# class EnumFlagField(EnumFieldMixin, IntFlagField):

#     _base_enum_type = BaseIntFlag


