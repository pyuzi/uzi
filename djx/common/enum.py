from dataclasses import Field, field, make_dataclass, fields as dataclass_fields, is_dataclass
from collections.abc import MutableMapping, Mapping, Iterable
from enum import (
    EnumMeta as BaseEnumMeta,
    Enum as BaseEnum, 
    IntEnum as BaseIntEnum,
    IntFlag as BaseIntFlag,
    Flag as BaseFlag,
)
from itertools import chain
from types import MappingProxyType
import warnings
import typing as t

from .utils import export, text


__all__ = []



# def __json__(self):
#     return self.value

# BaseEnum.__json__ = __json__
# del __json__



def _get_member_names(attrs, factory=list, default=None):
    f = factory and callable(factory) \
        and (lambda: factory((a for a in attrs if a[0] == '_' == a[-1])))
    return getattr(attrs, '_member_names', f and f() or default)



_MT = t.TypeVar('_MT', 'Enum', 'Flag', 'IntEnum', 'IntFlag', 'StrEnum')
_PV = t.TypeVar('_PV', bound=MutableMapping)


class member_property(property, t.Generic[_PV, _MT]):

    __slots__ = ('name',)

    def __init__(self, fget=None, fset=None, fdel=None, doc=None) -> None:
        super().__init__(fget=fget, fset=fset, fdel=fdel, doc=doc)
        self.name = None if fget is None else fget.__name__

    def __set_name__(self, owner, name):
        if self.name == (self.fget and self.fget.__name__ or None):
            self.name = name
        elif name != self.name:
            raise TypeError(
                "Cannot assign the same member_property to two different names "
                f"({self.name!r} and {name!r})."
            )

    def __get__(self, obj:  t.Optional[_MT], type: t.Optional[type[_MT]]) -> _PV:
        if obj is None:
            return self
        elif self.fget is None:
            return getattr(type.__member_data__[obj.name], self.name)
        return super().__get__(obj, type=type)


class _MemberData:
    def __post_init__(self):
        if self._name is not None and self.label is None:
            object.__setattr__(self, 'label', text.humanize(self._name).title()) 



class EnumMeta(BaseEnumMeta):

    def __new__(mcs, name, bases, attrs, fields=None, **kwds):

        get_member_names = \
              lambda d=None, f=list, *, a=attrs: _get_member_names(a, f, d)

        if fields is None and '__properties__' in attrs:
            warnings.warn(
                f'ClassVar __properties__ in {name}. '
                f'New syntax:  class {name}('
                f'{", ".join(b.__name__ for b in bases)}, '
                f'fields={attrs["__properties__"]!r}, defaults=`prop defaults`)', 
                DeprecationWarning, 
                stacklevel=2
            )
            
            if '__property_defaults__' in attrs:
                raise AttributeError(
                    f'{name}.__property_defaults__ no longer suppoted. '
                    f'Use the new syntax.'
                )

            fields = attrs.pop('__properties__')


        # if fields is not None:
        dcls = attrs['__member_dataclass__'] = mcs._define_member_dataclass(name, bases, fields)

        data = attrs['__member_data__'] = {}

        mnames = get_member_names(False, [])
        
        for i in range(len(mnames)):
            mname = mnames[i]	
            value = attrs.get(mname)
            if isinstance(value, tuple):
                value, *fargs = value
                attrs.update({mname:value})
            else:
                fargs = ()
            
            data[mname] = dcls(*fargs, _name=mname)
            
        for f in dataclass_fields(dcls):	
            if f.name not in {'_name', '_value'}:
                attrs.setdefault(f.name, member_property())
        
        cls = BaseEnumMeta.__new__(mcs, name, bases, attrs)

        return cls

    @classmethod
    def __prepare__(mcls, name, bases, *, fields=None) -> None: 
        rv = super().__prepare__(name, bases)
        return rv

    @classmethod
    def _define_member_dataclass(mcls, name, bases, fieldset=None, **kwds) -> type[tuple]:
        
        fields: Iterable = ()

        mapfn = lambda f: (
            (f, t.Any, field(default=None))
                if isinstance(f, str)
                else (f.name, f.type, f)
                if isinstance(f, Field) 
                else chain(f := [*f], [t.Any, field(default=None)][len(f)-1:])
            )
        
        if is_dataclass(fieldset):
            dbase = fieldset
        elif isinstance(fieldset, str):
            dbase = make_dataclass(
                    f'_{name}DataclassAbc',
                    map(mapfn, text.compact(fieldset.replace(',', ' ')).split()),
                    frozen=True
                )
        else:
            dbase = make_dataclass(
                    f'_{name}DataclassAbc',
                    map(mapfn, fieldset or ()),
                    frozen=True
                )

        ebase = bases[-1] if bases else None
        if issubclass(ebase, BaseEnum) and hasattr(ebase, '__member_dataclass__'):
            skip = dict((f.name, f) for f in dataclass_fields(dbase))
            skipfn = lambda f: f.name not in skip
            fields = map(mapfn, filter(skipfn, dataclass_fields(ebase.__member_dataclass__)))
        else:
            fields = [
                ('label', str, field(default=None)),
                ('_name', str, field(default=None)),
            ]

        return make_dataclass(
                f'_{name}Dataclass', 
                fields, 
                bases=(dbase, _MemberData), 
                frozen=True
            )

    def _choices_(cls):
        empty = ((None, cls.__empty__),) if hasattr(cls, '__empty__') else ()
        return empty + tuple((m.value, m.label) for m in cls)

    choices = _choices_

    @property
    def __values__(cls):
        """
        Returns a mapping of values value->member.

        Note that this is a read-only view of the internal mapping.
        """
        return MappingProxyType(cls._value2member_map_)



@export()
class Enum(BaseEnum, metaclass=EnumMeta):
    __slots__ = ()

    name: str
    label: str
    value: t.Any



@export()
class Flag(BaseFlag, metaclass=EnumMeta):
    __slots__ = ()

    name: str
    label: str
    value: t.Any


@export()
class IntEnum(BaseIntEnum, metaclass=EnumMeta):
    __slots__ = ()

    name: str
    label: str
    value: t.Any


@export()
class IntFlag(BaseIntFlag, metaclass=EnumMeta):
    __slots__ = ()

    name: str
    label: str
    value: t.Any

@export()
class StrEnum(str, Enum):
    __slots__ = ()

    name: str
    label: str
    value: t.Any
