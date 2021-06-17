import typing as t 
from functools import partial
from collections.abc import MutableMapping, Callable
from django.db import models as m
from django.core import validators
from django.db.models.fields.json import KeyTransform
from django.db.models.query_utils import DeferredAttribute

from djx.common import json
from djx.common.collections import MappingObject
from djx.common.utils import text, export, cached_property


class _RawJson(str):
    __slots__ = ()

@export()
class JSONField(m.JSONField):
    """JSONField Object"""

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        # Some backends (SQLite at least) extract non-string values in their
        # SQL datatypes.
        if isinstance(expression, KeyTransform) and not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return _RawJson(value)

    def get_prep_value(self, value):
        if value is None or isinstance(value, _RawJson):
            return value
        return json.dumps(value).decode()

    def validate(self, value, model_instance):

        m.Field.validate(self, value, model_instance)
        
        try:
            json.dumps(value)
        except TypeError:
            raise m.ValidationError(
                self.error_messages['invalid'],
                code='invalid',
                params={'value': value},
            )

    def formfield(self, **kwargs):
        return m.Field.formfield(self, **kwargs)




class JSONObjectDescriptor(DeferredAttribute):

    field: 'JSONObjectField'
    
    def __get__(self, obj, cls=None):
        if obj is None:
            return self

        name = self.field.attname
        try:
            return obj.__dict__[name]
        except KeyError:
            self.__set__(obj, super().__get__(obj, cls))
            return obj.__dict__[name]

    def __set__(self, obj, val):
        f = self.field
        name = f.attname
        cls = f.object_type
        if isinstance(val, cls) or (val is None and f.null):
            obj.__dict__[name] = val

        func = f.object_factory or cls
        if val is None and f.blank:
            obj.__dict__[name] = (f.has_default() and f.get_default or func)()
        else:
            obj.__dict__[name] = func(val)

    def __delete__(self, obj):
        try:
            del obj.__dict__[self.field.attname]
        except KeyError:
            pass
        


_T_JSONObject = t.TypeVar('_T_JSONObject', json.Jsonable, MappingObject)


@export()
class JSONObjectField(JSONField, t.Generic[_T_JSONObject]):
    """JSONObjectField """

    descriptor_class = JSONObjectDescriptor
    empty_strings_allowed = False
    
    if t.TYPE_CHECKING:
        def __new__(self, 
                *args, 
                type: type[_T_JSONObject]=MappingObject, 
                factory: Callable[[t.Any], _T_JSONObject]=None, 
                **kwargs) -> _T_JSONObject:
            ...    

    def __init__(self, 
                *args, 
                type: type[_T_JSONObject]=MappingObject, 
                factory: Callable[[t.Any], _T_JSONObject]=None, 
                **kwargs) -> None:
        self.object_type = type
        self.object_factory = factory
        super().__init__(*args, **kwargs)
    
    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        
        if self.object_type is not MappingObject:
            kwargs['type'] = self.object_type

        if self.object_factory is not None:
            kwargs['factory'] = self.object_factory

        return name, path, args, kwargs




_T_AutoSlugFunc = t.Callable[[m.Model, t.Optional[str]], t.Optional[str]]


@export()
class SlugField(m.SlugField):

    pathlike = False

    _auto_field_add_overrides = dict(
        blank=True,
    )

    _auto_field_overrides = dict(
        blank=True,
        editable=False
    )


    def __init__(self, *args, 
                auto_field: t.Union[str, _T_AutoSlugFunc]=None, 
                auto_field_add: t.Union[str, _T_AutoSlugFunc]=None, 
                auto_suffix:bool=None,
                similar_with: m.Q=None, 
                allow_chars: str='', 
                max_length=128,
                coerce=False, 
                **kwargs):

        if not (None is auto_field is auto_field_add):
            kwargs.get('null') and kwargs.setdefault('default', '')

            if auto_field_add is not None:
                kwargs.update(self._auto_field_add_overrides)

            if auto_field is not None:
                kwargs.update(self._auto_field_overrides)

        self.coerce = coerce
        self.allow_chars = allow_chars
        self.auto_field = auto_field
        self.auto_field_add = auto_field_add
        self.similar_with = similar_with
        self.auto_suffix = auto_suffix or False
        
        super().__init__(*args, max_length=max_length, **kwargs)


    @cached_property
    def default_validators(self):
        return [self.slug_validator]

    @cached_property
    def _auto_add_func(self) -> t.Callable[[m.Model, str], str]:
        if self.auto_field_add:
            if callable(self.auto_field_add):
                def func(obj, val):
                    val = self.auto_field_add(obj, val)
                    return self.slugify(val) if val else val
            else:
                def func(obj, val):
                    if not val:
                        val = getattr(obj, self.auto_field_add, val)
                    return self.slugify(val) if val else val
            
            # if self.auto_suffix:
            #     fn = func
            #     def func(obj: m.Model, val):
            #         qs = obj.__class__._default_manager.            

            return func
        return self._auto_func

    @cached_property
    def _auto_func(self) -> t.Callable[[m.Model, str], str]:
        if self.auto_field:
            if callable(self.auto_field):
                def func(obj, val):
                    val = self.auto_field(obj, val)
                    return self.slugify(val) if val else val
            else:
                def func(obj, val):
                    val = getattr(obj, self.auto_field, val)
                    return self.slugify(val) if val else val

        else:
            def func(obj, val):
                if self.coerce:
                    val = val and self.slugify(val)
                return val

        return func
        

    @cached_property
    def slug_validator(self):
        s_re = text.slug_re(allow=self.allow_chars, pathlike=self.pathlike)
        return validators.RegexValidator(s_re, inverse_match=True)

    @cached_property
    def slugify(self):
        return partial(text.slug, allow=self.allow_chars, pathlike=self.pathlike)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if kwargs.get("max_length") == 128:
            del kwargs['max_length']

        if self.coerce is not False:
            kwargs['coerce'] = self.coerce

        if self.allow_chars != '':
            kwargs['allow_chars'] = self.allow_chars

        if self.similar_with is not None:
            kwargs['similar_with'] = self.similar_with

        if self.auto_suffix:
            kwargs['auto_suffix'] = self.auto_suffix

        if self.auto_field is not None:
            kwargs['auto_field'] = self.auto_field
            for k in self._auto_field_overrides: del kwargs[k]

        if self.auto_field_add is not None:
            kwargs['auto_field_add'] = self.auto_field
            for k in self._auto_field_add_overrides: del kwargs[k]

        return name, path, args, kwargs

    def pre_save(self, model_instance, add):
        value = super().pre_save(model_instance, add)
        if value is None and self.null:
            return None
        elif add:
            return self._auto_add_func(model_instance, value)
        else:
            return self._auto_func(model_instance, value)

        # if not value:
        #     # if add and self.auto_field_add is not None:
                
        #     if self.auto_field:
        #         if (default := getattr(model_instance, self.auto_field, None)):
        #             setattr(model_instance, self.attname, (value := self.slugify(default)))
        # elif self.coerce:
        #     setattr(model_instance, self.attname, (value := self.slugify(value)))
        # else:
        #     self.slug_validator(value)
        # return value




@export()
class PathLikeSlugField(SlugField):
    """PathlikeSlugField model field"""
    
    pathlike = True
    

