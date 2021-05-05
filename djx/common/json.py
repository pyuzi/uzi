from __future__ import annotations
from abc import ABCMeta, abstractmethod
from dataclasses import is_dataclass
import uuid
import decimal
import typing as t
import datetime
import warnings
import json as stdjson


from functools import partial
from djx.common.collections import fallbackdict
from djx.common.utils import export

try:
    import orjson
    _json = orjson
except ImportError:
    orjson: t.Any = None
    _json = stdjson




_SET_TYPES = set, frozenset
_DATE_TIME_TYPES = datetime.date, datetime.time, datetime.datetime




def _get_default_encoder(typ):
    if issubclass(typ, Jsonable):
        _ENCODERS[typ] = typ.__json__
    elif issubclass(typ, _DATE_TIME_TYPES):
        _ENCODERS[typ] = typ.isoformat # _encode_date_type
    elif issubclass(typ, (decimal.Decimal, uuid.UUID)):
        _ENCODERS[typ] = str
    elif issubclass(typ, (t.Sequence, t.Set)):
        _ENCODERS[typ] = tuple
    elif issubclass(typ, t.Mapping):
        _ENCODERS[typ] = dict
    else:
        _ENCODERS[typ] = None
    return _ENCODERS[typ]
    

_ENCODERS = fallbackdict(_get_default_encoder)


 


JSONDecodeError = stdjson.JSONDecodeError


@export()
class Jsonable(metaclass=ABCMeta):

    @classmethod
    def __subclasshook__(cls, klass) -> bool:
        if cls is Jsonable:
            return hasattr(klass, '__json__') or is_dataclass(klass)
        return NotImplemented

    @abstractmethod
    def __json__(self) -> Jsonable:
        ...


# for t in _SET_TYPES + _DATE_TIME_TYPES + (str, bytes, int, float, tuple, list, dict, decimal.Decimal):
#     Jsonable.register(t)

# del t




@export()
class JSONEncoder(stdjson.JSONEncoder):
    """
    JSONEncoder subclass that knows how to encode date/time, decimal types and UUIDs.
    """
    def default(self, o):
        return to_jsonable(o, default=super().default)
    


@export()
class JSONDecoder(stdjson.JSONDecoder):
    """The default JSON decoder.  This one does not change the behavior from
    the default simplejson decoder.  Consult the :mod:`json` documentation
    for more information.  This decoder is not only used for the load
    functions of this module but also :attr:`~flask.Request`.
    """
    ...




def to_jsonable(o, /, *, default=None):
    # See "Date Time String Format" in the ECMA-262 specification.
    enc = _ENCODERS[type(o)]
    if enc is None and (enc := default) is None:
        raise TypeError(o)
    return enc(o) 
        







@export()
def dumpb(obj: Jsonable, *, default: t.Callable[[t.Any], Jsonable]=to_jsonable) -> bytes:
    """Serialize ``obj`` to a JSON formatted ``bytes``
    Uses ``orjson`` if available or falls back to the standard ``json`` library.
    """
    default is to_jsonable or (default := partial(to_jsonable, default=default))
    return _json.dumps(obj, default=default)

    


@export()
def dumps(obj: Jsonable, *, default: t.Callable[[t.Any], Jsonable]=to_jsonable) -> str:
    """Serialize ``obj`` to a JSON formatted ``bytes`` or ``str``.
    Uses ``orjson`` if available or falls back to the standard ``json`` library.
    """
    return dumpb(obj, default=default).decode()



@export()
def loads(s, **kwargs):
    """Unserialize a JSON object from a string ``s``.
    Uses ``orjson`` if available or falls back to the standard ``json`` library.
    """
    if kwargs:
        return stdjson.loads(s, **kwargs)
    else:
        return _json.loads(s)

