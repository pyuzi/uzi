import typing as t 
from functools import partial
from django.db import models as m
from django.core import validators
from djx.common.utils import text, export, cached_property


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
        if not self.auto_field_add:
            return self._auto_func
    
        if callable(self.auto_field_add):
            def func(obj, val):
                if not val:
                    val = self.auto_field_add(obj, val)
                return self.slugify(val) if val else val
        else:
            def func(obj, val):
                if not val:
                    val = getattr(obj, self.auto_field_add, val)
                return self.slugify(val) if val else val
        return func
    
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
            value = self._auto_add_func(model_instance, value)
        else:
            value = self._auto_func(model_instance, value)

        setattr(model_instance, self.attname, value)
        return value

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
    

