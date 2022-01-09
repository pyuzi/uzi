from logging import getLogger
from types import new_class
import typing as t

from itertools import groupby
from django.db import models as m

from collections.abc import Set
from jani.common.collections import fallback_chain_dict, fallback_default_dict, fallbackdict, orderedset
from jani.common.metadata import metafield


from jani.common.functools import (
    export, cached_property
)
from jani.common.data import DataPath, result

from ..config import ModelConfig



_T_Model = t.TypeVar('_T_Model', bound='Model', covariant=True)

logger = getLogger(__name__)


if t.TYPE_CHECKING:
    from django.db.models.fields import Field
    from ..base import Model






@export()
class PolymorphicModelConfig(ModelConfig):

    is_polymorphic: bool = True

    @metafield
    def polymorphic_ctype_field_name(self, value, base=None):
        return value or base or 'polymorphic_ctype'

    @property
    def polymorphic_ctype(self):
        return self.polymorphic_concrete.__config__.model_ctype or ...

    @property
    def polymorphic_concrete(self):
        if self.polymorphic_proxy:
            return self.parent.polymorphic_concrete
        return self.target

    @metafield[bool]
    def polymorphic_proxy(self, value, base=None):
        if value is None:
            return base
        elif not value:
            assert not base, (f'polymorphic_proxy {value=} {base=}') 
        else:
            assert self.parent and self.parent.is_polymorphic, (f'polymorphic_proxy {value=} {self.parent=}') 

        return value

    @metafield
    def polymorphic_on(self, value, base=None) -> t.Optional[fallback_chain_dict[str, t.Any]]:
        if not base:
            base = { self.polymorphic_ctype_field_name : DataPath('polymorphic_ctype') }
        
        return fallback_chain_dict(base, value or ())

    @cached_property
    def polymorphic_values(self) -> dict[str, t.Any]:
        if not self.abstract:
            if raw := self.polymorphic_on:
                rv = { k: result(raw[k], self) for k in raw }
                return rv

    @cached_property
    def polymorphic_ctype_field(self):
        if fields := self.polymorphic_fields:
            if name := self.polymorphic_ctype_field_name:
                for field in fields:
                    if field.alias == name:
                        return field

    @cached_property[t.Optional['ModelConfig']]
    def polymorphic_base(self) -> t.Optional['ModelConfig']:
        if not self.abstract and self.is_polymorphic:
            if self.proxy:
                return self.parent and self.parent.polymorphic_base
            else:
                return self

    @cached_property[t.Optional['ModelConfig']]
    def polymorphic_root(self) -> t.Optional['ModelConfig']:
        if not self.abstract:
            if  self.parent and self.parent.is_polymorphic:
                return self.parent.polymorphic_root
            else:
                return self

    @cached_property
    def polymorphic_descendants(self) -> int:
        count = 0
        if types := self.polymorphic_types:
            for typ in types.values():
                if typ is not self.target:
                    count += 1
        return count

    @cached_property
    def polymorphic_fields(self) -> t.Union[orderedset['_PolymorphicField'], None]:
        if not self.abstract:
            if values := self.polymorphic_on:
                fields: list[_PolymorphicField] = []
                fieldset = [f.attname for f in self.modelmeta.concrete_fields]

                fcls = _PolymorphicField[self.polymorphic_root.target]

                for name in values:
                    field = self.get_field(name, None)
                    if field is None:
                        if aka := self.get_alias_fields().get(name):
                            if luk := aka.lookup_path or aka.lookup_expr_path:
                                field = self.get_field(luk.lookup, None)
                    if field is None:
                        raise ValueError(f'polymorphic field {name!r} does not exist in {self.target}')

                    fields.append(fcls(field, fieldset.index(field.attname), name))
                
                return orderedset(sorted(fields))

    # @cached_property
    # def polymorphic_key(self) -> t.Union[tuple['_PolymorphicValue'], None]:
    #     if fields := self.polymorphic_fields:
    #         vals = self.polymorphic_values

    #         return tuple(f.values(v) for f in fields if (v := vals[f.alias]) is not ...) or None
    
    @cached_property
    def polymorphic_keys(self) -> t.Union[tuple['_PolymorphicValue'], None]:
        if fields := self.polymorphic_fields:
            vals = self.polymorphic_values
            return orderedset(v for f in fields for v in f.values(vals[f.alias])) or None
    
    @cached_property[bool]
    def polymorphic_loading(self) -> bool:
        return self.polymorphic_descendants and not self.polymorphic_proxy

    @cached_property
    def polymorphic_args(self) -> dict[tuple[int], dict[tuple[t.Any], type[_T_Model]]]:
        if self.polymorphic_descendants:
            if types := self.polymorphic_types:
                ct_field = self.polymorphic_ctype_field

                ctypes  = fallbackdict()

                for k in types:
                    if keys := tuple(f for f in (k,) if f.field == ct_field):
                        kf = keys[0]
                        val = v if kf.field.is_relation and (v := getattr(kf.value, 'pk', None)) is not None else kf.value
                        ctypes[val] = types[k]
                    
                return ct_field.index, ctypes
        
    @cached_property
    def polymorphic_kwargs(self) -> dict[tuple[str], dict[tuple[t.Any], type[_T_Model]]]:
        if self.polymorphic_descendants:
            if types := self.polymorphic_types:
                kwargmaps  = fallback_default_dict(lambda k: fallbackdict())
                ct_field = self.polymorphic_ctype_field

                ctypes = kwargmaps[(ct_field.alias,)]
                for k in types:
                    if keys := tuple(f for f in (k,) if f.field == ct_field):
                        ctypes[keys[0].value] = types[k]

                skip = {ct_field} # {ct_field, *(f.field for f in self.polymorphic_key or ())}
                
                for k in types:
                    if keys := tuple(f for f in (k,) if f.field not in skip):
                        key = tuple(f.field.alias for f in keys)
                        val = tuple(f.value for f in keys)
                        kwargmaps[key][val] = types[k]

                # skip = { ct_field, *(f.field for f in self.polymorphic_key or ())}
                # for k in types:
                #     if keys := tuple(f for f in k if f.field not in skip):
                #         key = tuple(f.field.alias for f in keys)
                #         val = tuple(f.value for f in keys)
                #         kwargmaps[key][val] = types[k]

                return tuple(kwargmaps.items())
        
    @cached_property
    def polymorphic_types(self) -> t.Optional[dict[tuple['_PolymorphicValue'], type[_T_Model]]]:
        if tree := self.polymorphic_tree:
            if self is self.polymorphic_root:
                val = tree
            else:
                val = {k : v for k,v in tree.items() if issubclass(v, self.model)}
            return { k:val[k] for k in sorted(val, key=lambda k: tuple([len(k), k])) }

    @cached_property
    def polymorphic_tree(self) -> t.Optional[dict[tuple['_PolymorphicValue'], type[_T_Model]]]:
        if  self.polymorphic_fields:
            root = self.polymorphic_root
            keys = self.polymorphic_keys or ()
            if root is self:
                tree = dict()
            else:
                tree = root.polymorphic_tree

            if keys:
                dups = []
                if self.polymorphic_proxy:
                    if (f := next(self.polymorphic_ctype_field.values(self.model_ctype))).value is not None:
                        mod = tree.setdefault(f, self.model)
                        mod is self.model or dups.append(f)
                else:
                    tree.update(((k, self.model) for k in keys if k not in tree or dups.append(k)))
                

                if dups:
                    raise ValueError(f'Duplicate polymorphic values: {(f"  {f!r} on {self.model} and {tree[f]}" for f in dups)}')

                # vals = self.polymorphic_values
                self.initial_kwargs.update((f.alias, next(g).value) for f, g in groupby(keys, key=lambda k: k.field))
                    # k = next(g)
                    # self.initial_kwargs(k.alias, k.value)

                # if k := keys[0]:
                    # self.initial_kwargs.setdefault(k.alias, vals[k.alias])
            return tree



class _PolymorphicValue(t.NamedTuple('_PolymorphicFieldValue', [('field', '_PolymorphicField'), ('value', t.Any)])):

    __slots__ = ()

    # value: t.Any
    _field_attrs = frozenset(( 'index', 'alias', 'name', 'attname', 'root'))

    root: type[_T_Model]
    alias: str
    name: str
    attname: str
    
    index: int
    field: '_PolymorphicField'

    def __getattr__(self, name):
        if name in self._field_attrs:
            return getattr(self.field, name)
        raise AttributeError(name)

    def __gt__(self, o) -> bool:
        if isinstance(o, _PolymorphicValue):
            return self.field > o.field
        return self.field > o
    
    def __ge__(self, o):
        return self.__gt__(o) or self.__eq__(o)

    def __lt__(self, o) -> bool:
        if isinstance(o, _PolymorphicValue):
            return self.field < o.field
        return self.field < o

    def __le__(self, o):
        return self.__lt__(o) or self.__eq__(o)



def _new_polymorphic_field_class(typ: type[_T_Model]) -> '_PolymorphicField[_T_Model]':
    return new_class(f'_{typ.__name__}PolymorphicField', (_PolymorphicField[_T_Model],), None, lambda ns: ns.update(root=typ))


class _PolymorphicField(t.Generic[_T_Model]):

    __slots__ = 'index', 'alias', 'field', '_hash',

    root: type[_T_Model]
    alias: str
    name: str
    attname: str
    
    index: int
    field: 'Field'

    __by_root = fallback_default_dict[type[_T_Model], type['_PolymorphicField[_T_Model]']](_new_polymorphic_field_class)

    def __class_getitem__(cls, params):
        if isinstance(params, tuple):
            typ = params[0]
        else:
            typ = params
        
        if isinstance(typ, type):
            _cls = cls.__by_root[typ] 
            return super(cls, _cls).__class_getitem__(params)

        return super().__class_getitem__(params)

    def __new__(cls, field, index=None, alias=None) -> None:
        if field.__class__ is cls:
            field = field.field

        self = super().__new__(cls)
        self.field = field
        self.alias = alias or field.name
        self.index = index
        return self

    def values(self, v):
        val = result(v, self)
        if isinstance(val, list):
            for x in val:
                yield from self.values(x)
        elif val is not ...:
            yield _PolymorphicValue(self,  val)
            if self.field.is_relation and isinstance(val, m.Model) and val.pk is not None:
                yield _PolymorphicValue(self, val.pk)

    def __eq__(self, o):
        typ = o.__class__
        if issubclass(typ, _PolymorphicField):
            return self.index == o.index \
                and (issubclass(o.root, self.root) or issubclass(self.root, o.root))
        elif typ is str:
            return self.alias.__eq__(o)
        elif typ is int:
            return self.index.__eq__(o)
        else:
            return (self.root, self.index).__eq__(o)

    def __reduce__(self):
        return self.__class__, (self.field, self.index, self.index)
    
    def __gt__(self, o) -> bool:
        typ = o.__class__
        if issubclass(typ, _PolymorphicField):
            return self.index.__gt__(o.index)
        elif typ is str:
            return self.alias.__gt__(o)
        else:
            return self.index.__gt__(o)
    
    def __ge__(self, o):
        return self.__gt__(o) or self.__eq__(o)

    def __lt__(self, o) -> bool:
        typ = o.__class__
        if issubclass(typ, _PolymorphicField):
            return self.index.__lt__(o.index)
        elif typ is str:
            return self.alias.__lt__(o)
        else:
            return self.index.__lt__(o)
    
    def __le__(self, o):
        return self.__lt__(o) or self.__eq__(o)
    
    def __hash__(self) -> int:
        try:
            return self._hash
        except AttributeError:
            self._hash = hash((self.root, self.index))
            return self._hash
    
    def __getattr__(self, name):
        if name != '_hash':
            return getattr(self.field, name)
        raise AttributeError(name)
    
    def __int__(self) -> int:
        return self.index

    def __str__(self) -> str:
        return self.alias

    def __repr__(self) -> str:
        return f'PolymorphicField({self.alias!r}, {self.root})'



if t.TYPE_CHECKING:
    class _PolymorphicField(Field, _PolymorphicField):
        ...

