from abc import ABCMeta
from functools import partial
import re
import typing as t

import uuid
from types import MappingProxyType, new_class
from pathlib import Path, PurePath
from weakref import finalize
from django.template import ( 
    Engine as BaseEngine,  engines, EngineHandler, 
    exceptions
)

from collections.abc import Hashable, Sequence
from jani.common.collections import orderedset, fallback_chain_dict, fallbackdict
from jani.common.imports import ImportRef
from jani.common.proxy import unproxy
from jani.common.utils.data import assign, delitem, getitem
from jani.common.saferef import SafeReferenceType, saferef

from jani.core import settings
from jani.abc import Renderable

from django.template.backends.base import BaseEngine as Backend


if t.TYPE_CHECKING:
    from jinja2 import Environment
else:
    Environment = t.Any



def to_renderable(val, using=None):
    if isinstance(val, Renderable):
        return val
    elif isinstance(val, RawTemplate):
        return val.compile(using)
    elif isinstance(val, ImportRef):
        return get_engine(val())
    else:
        return RawTemplate(val).compile(using)





def get_engine(eng=None):
    if isinstance(eng, Engine):
        return eng
    elif isinstance(eng, ImportRef):
        return get_engine(eng())
    elif eng is None:
        return engines[next(iter(engines))]
    else:
        return engines[str(eng)]




class Engine(BaseEngine, metaclass=ABCMeta):
    name: str


Engine.register(Backend)


def _hash_id(val):
    if isinstance(val, Hashable):
        return hash(val)
    else:
        return hash((id, val.__class__, id(val)))


class RawTemplate:

    __slots__ = ('name', 'raw', '_context', '_hash', '_compiled', '__weakref__')

    name: t.Union[str, None]
    raw:  t.Union[str, Renderable, 'RawTemplate']
    context: dict

    def __new__(cls, raw: t.Union[str, Renderable, 'RawTemplate'], name: str=None, /, **context):
        self: cls = super().__new__(cls)
        self.raw = raw
        self.name = name
        self._context = MappingProxyType(context)
        self._compiled = fallbackdict()
        return self

    @property
    def context(self):
        return self._context

    def __hash__(self) -> int:
        try:
            return self._hash
        except AttributeError:
            self._hash = hash((self.name, self.raw, *sorted((k, _hash_id(v)) for k,v in self.context)))
            return self._hash

    def __eq__(self, o) -> int:
        if isinstance(o, RawTemplate):
            return o is self or self.name == o.name \
                and self.raw == o.raw \
                and self._context == o._context
        return NotImplemented

    def __repr__(self):
        return f'{self.__class__.__name__}({self.raw!r}, {self.context})'

    def __str__(self):
        return repr(self)

    def __bool__(self):
        return True

    def __len__(self):
        return len(self.context)

    def __contains__(self, key):
        return key in self.context

    # def __getitem__(self, key):
    #     return self.context[key]

    # def __delitem__(self, key):
    #     del self.context[key]

    # def __setitem__(self, key, value):
    #     self.context[key] = value

    def __getnewargs_ex__(self):
        return (self.name, self.raw), self.context

    def clone(self, name=None, /, **context):
        context = {**self.context, **context} if context else self.context
        return self.__class__(self.raw, name, **context)

    def copy(self, **context):
        return self.clone(self.name, **context)
    
    __copy__ = copy

    def compile(self, engine: Engine=None) -> str:
        engine = get_engine(engine)
        ck = (getattr(engine, 'name', None), engine.__class__, id(engine))

        rv = self._compiled[ck]
        if not rv:
            raw = self.raw
            typ = raw.__class__
            
            if issubclass(typ, ImportRef):
                raw = raw()
                typ = raw.__class__
            
            if issubclass(typ, Renderable):
                rv = raw
            elif issubclass(typ, TemplateName):
                rv = engine.get_template(raw)
            elif issubclass(typ, str):
                rv = engine.from_string(raw)
            elif issubclass(typ, RawTemplate):
                rv = raw.compile(engine)
            elif issubclass(typ, Sequence):
                rv = engine.select_template(raw)
            else:
                raise exceptions.TemplateSyntaxError(self)

            self._compiled[ck] = TemplateWrapper(rv, self.context)
            finalize(engine, self._pop_compiled_, saferef(self), ck)
            
        return rv

    @staticmethod
    def _pop_compiled_(ref: SafeReferenceType['RawTemplate'], key) -> None:
        if tmp := ref():
            tmp._compiled.pop(key, None)
        


class TemplateWrapper:

    __slots__ = 'template', 'context',

    def __init__(self, template, context=None) -> None:
        self.template = template
        self.context = context or {}

    def render(self, *args, **kwds):
        return self.template.render(fallback_chain_dict(self.context or {}, *args, **kwds))



class RenderedTemplateWrapper(TemplateWrapper):

    __slots__ = ()

    def __init__(self, template, context=None) -> None:
        self.template = template
        self.context = context
        assert not context

    def render(self, *args, **kwds):
        return self.template






class TemplateName(str):

    __slots__ = ()

    allowed_patterns = orderedset(getitem(settings, 'TEMPLATE_NAME_PATTERNS', None) or (r'[A-Za-z0-9_-]+\.[A-Za-z0-9_-]{2,16}$',))
    forbiden_check = r'[\{\}\n\<>]+'

    @classmethod
    def Constr(cls, *patterns) -> None:
        return new_class('ConstrTemplateName', (cls,), None, lambda ns: ns.update(allowed_patterns=orderedset(patterns)))

    @property
    def path(self):
        return Path(self)

    @classmethod
    def __modify_schema__(cls, field_schema) -> None:
        field_schema.update(type='string', format='path')

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if v.__class__ is cls:
            v = unproxy(v)
        elif isinstance(v, str):
            v = cls(v)
        elif isinstance(v, PurePath):
            v = cls(v)

        if cls.forbiden_check and re.search(cls.forbiden_check, v):
            raise ValueError('invalid template name')

        v.path
        for r in cls.allowed_patterns:
            if re.search(r, v):
                return v

        raise ValueError('invalid template name')




define_template = RawTemplate
rawtemplate = RawTemplate


