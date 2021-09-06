import re
from abc import ABCMeta

import copy as _copy
import logging
import typing as t

from types import MethodType

from collections import ChainMap
from collections.abc import Mapping, Callable
from threading import RLock

from djx.common.collections import orderedset
from djx.common.utils.data import assign



from .utils import export, Void


METADATA_ATTR = '_meta'
METADATA_CLASS_ATTR = '__metadata_class__'


# _class_registry = dict()

logger = logging.getLogger('flex')

T = t.TypeVar('T')

def get_metadata_class(cls: t.Type[T], attr: str, 
                        final_attr: t.Optional[str] = None, 
                        base: t.Type['BaseMetadata'] = None,
                        mro: t.Optional[t.Tuple[t.Type, ...]] = None, 
                        name: t.Optional[str] = None, 
                        dct: t.Optional[t.Mapping] = None, 
                        set_final: t.Optional[bool] = False) -> t.Type['BaseMetadata[T]']:
    
    rv = final_attr and getattr(cls, final_attr, None)
    if not rv:
        bases = tuple(_iter_base_metadata_class(attr, mro or cls.mro(), base))
        rv = type(name or f'{cls.__name__}Metadata', bases, dct or {})

    return rv




def _iter_base_metadata_class(attr, mro, base=None):
    seen = set((None,))

    for c in mro:
        oc = getattr(c, attr, None)
        if oc not in seen:
            seen.update(oc.mro())
            yield oc

    base = base or BaseMetadata
    if base not in seen:
        yield base



__last_creation_index = 0


def _get_creation_order():
    global __last_creation_index
    __last_creation_index += 1
    return __last_creation_index


_TF = t.TypeVar('_TF')

@export
class metafield(property, t.Generic[_TF]):
    """Descriptor for meta fields.
    """

    __slots__ = (
        '__name__', '__objclass__', 'doc', 'field',
        'fload', 'fget', 'fset', 'fdel', '_creation_order',
        'access', 'inherit', 'default', 'lock',
    )

    def __init__(self, fload=None, field=None, fget=None, fset=None, fdel=None,
                name=None, default=None, inherit=True, doc=None):
        self.fload = self.fget = self.fset = self.fdel = None

        self.__name__ = name
        self.__objclass__ = None
        self.doc = doc

        if isinstance(fload, str):
            assert field is None
            self.field = fload
            fload = None
        else:
            self.field = field


        self.loader(fload)
        self.getter(fget)
        self.setter(fset)
        self.deletter(fdel)

        self.default = default
        self.inherit = inherit
        self.lock = RLock()

        self._creation_order = _get_creation_order()

    @property
    def __doc__(self):
        return self.doc

    def loader(self, func):
        if func is None or callable(func):
            old = self.fload
            self.fload = func
            if self.doc is None or (old is not None and self.doc == old.__doc__):
                self.doc = None if func is None else func.__doc__
            if self.__name__ is None or (old is not None and self.__name__ == old.__name__):
                self.__name__ = None if func is None else func.__name__
        else:
            raise TypeError('expected callable, got %s.' % type(func))

    def getter(self, func):
        if func is None or callable(func):
            self.fget = func
        else:
            raise TypeError('Expected callable or None. Got %s.' % type(func))

    def setter(self, func):
        if func is None or callable(func):
            self.fset = func
        else:
            raise TypeError('Expected callable or None. Got %s.' % type(func))

    def deletter(self, func):
        if func is None or callable(func):
            self.fdel = func
        else:
            raise TypeError('Expected callable or None. Got %s.' % type(func))

    def contribute_to_class(self, owner, name=None):
        assert name is None or self.__name__ == name, (
                f'attribute __name__ must be set to bind {type(self)}'
            )

        if self.__objclass__:
            assert issubclass(owner, self.__objclass__), (
                f'can only contribute to subclasses of {self.__objclass__}. {owner} given.'
            )

    def __load__(self, obj) -> t.Union[_TF, t.Any]:
        try:
            rv = obj.__raw__[self.field or self.__name__]
        except (AttributeError, KeyError):
            rv = Void

        try:
            base = obj.__base__
        except AttributeError:
            base = None

        if self.fload is None:
            if rv is Void:
                if self.inherit and base is not None:
                    rv = base.get(self.__name__, self.default)
                else:
                    rv = self.default
        else:
            if not self.inherit or base is None:
                args = ()
            elif self.field in base:
                args = (base[self.field],)
            elif self.__name__ in base:
                args = (base[self.__name__],)
            else:
                args = ()
            rv = self.fload(obj, self.default if rv is Void else rv, *args)

        obj.__dict__[self.__name__] = rv
        return rv

    def __set_name__(self, owner, name):
        if self.__objclass__ is None:
            self.__objclass__ = owner
            self.__name__ = name
        elif self.__objclass__ is owner:
            self.__name__ = name
        else:
            raise RuntimeError(f'__set_name__. metafield already bound.')

    def __call__(self, fload: t.Callable[..., _TF]) -> 'metafield[_TF]':
        assert self.fload is None, ('metafield option already has a loader.')
        self.loader(fload)
        return self

    def __get__(self, obj, cls) -> _TF:
        if obj is None:
            return self

        with self.lock:
            try:
                rv = obj.__dict__[self.__name__]
            except KeyError:
                rv = self.__load__(obj)
            return rv if self.fget is None else self.fget(obj, rv)

    def __set__(self, obj, value):
        with self.lock:
            if self.fset is not None:
                obj.__dict__[self.__name__] = self.fset(obj, value)
            elif self.fload is not None:
                if self.inherit:
                    obj.__dict__[self.__name__] = self.fload(obj, value, obj.__dict__.get(self.__name__))
                else:
                    obj.__dict__[self.__name__] = self.fload(obj, value)
            else:
                obj.__dict__[self.__name__] = value

    def __delete__(self, obj):
        if self.fdel is not None:
            self.fdel(obj)
        obj.__dict__.pop(self.__name__, None)




class MetadataType(ABCMeta):

    def __new__(mcls, name, bases, dct):
        super_new = super(MetadataType, mcls).__new__

        # dct['__fields__'] = orderedset()

        cls = super_new(mcls, name, bases, dct)
        cls.register_metafields()
        return cls

    def register_metafields(self):
        self.__fields__= fieldset = orderedset()
        for name, field in self._iter_metafields():
            field.contribute_to_class(self, name)
            fieldset.add(name)
            field.field and fieldset.add(field.field)
        
    def _iter_metafields(self):
        fields = ((k,v) for k in dir(self)
                    for v in (getattr(self, k),) 
                        if isinstance(v, metafield)
                )

        mro = list(self.mro())
        mro.append(None)
        yield from sorted(fields, key=lambda kv: (mro.index(kv[1].__objclass__)+1)*kv[1]._creation_order)

        





def _to_dict(obj, default=None, skip: str=r'^__'):
    if obj is None:
        return default
    elif isinstance(obj, Mapping):
        return obj
    skip = skip and re.compile(skip).search
    skipfn = skip and (lambda v: not skip(v)) or None
    return { k: getattr(obj, k) for k in filter(skipfn, dir(obj)) }



TT = t.TypeVar('TT')

@export
class BaseMetadata(t.Generic[T], metaclass=MetadataType):

    __fields__: orderedset

    __name__: str
    __allowextra__: bool = False

    target: t.Type[T]

    def __init__(self, target = None, name=None, raw=None, base=None, *, allowextra=None):
        self.target = None

        # debug(name, raw, base)
        self.__raw__ = _to_dict(raw, default=dict())
        self.__base__ = _to_dict(base, skip=None)
        
        if allowextra is not None:
            self.__allowextra__ = allowextra

        # target and self.contribute_to_class(target, name)
        target is None or self.__set_name__(target, name)
        # if target is not None:
            # self.target = 
        
    @property
    def __objclass__(self) -> t.Type[T]:
        return self.target

    @property
    def _metadataloaded_(self):
        return not(hasattr(self, '__raw__') or hasattr(self, '__base__'))

    def __set_name__(self, owner, name):
        if self.target is None:
            if isinstance(owner, type):
                setattr(owner, name, self) 
            self.target = owner
            name and self.__load__(name)
        else:
            assert self.target is owner, (
                    f'{type(self)} already added to {self.target}. adding: {owner}.'
                )

    def __load__(self, name):
        if not hasattr(self, '__raw__'):
            raise RuntimeError(f'{type(self)} already loaded for {self.target}.')

        if self.__base__ is None and name:
            self.__base__ = self._base_from_target(self.target, name)

        self.__name__ = name

        for f in self.__fields__:
            getattr(self, f, None)

        if self.__allowextra__:
            skip = set(dir(self))
            for k in self.__raw__.keys():
                if k not in skip:
                    if isinstance(k, str) and not k.startswith('_'):
                        setattr(self, k, self.__raw__[k])
                        skip.add(k)

            for k in self.__base__.keys():
                if k not in skip:
                    if isinstance(k, str) and not k.startswith('_'):
                        setattr(self, k, self.__base__[k])

        self.__ready__()
        # name and setattr(self.target, name, self)

    def __ready__(self):
        del self.__raw__
        del self.__base__
    
    def copy(self, **replace):
        if not self._metadataloaded_:
            raise RuntimeError(f'{self.__class__.__name__} not loaded')
        rv = _copy.copy(self)
        replace and rv.__dict__.update(replace)
        return rv

    def __getstate__(self):
        if not self._metadataloaded_:
            raise RuntimeError(f'{self.__class__.__name__} not loaded')
        return self.__dict__.copy()
        
    def __setstate__(self, val):
        self.__dict__.update(val)

    @classmethod
    def _base_from_target(cls, target, attr):
        if isinstance(target, type):
            maps = (getattr(b, attr, None) for b in target.__bases__)
            maps = (_to_dict(b, skip=None) for b in maps if isinstance(b, BaseMetadata))
            return ChainMap({}, *maps)
        return getattr(target.__class__, attr, {})
        

    # def contribute_to_class(self, owner, name=None):
    #     name and owner and setattr(owner, name, self) 
    #     self.__set_name__(owner, name)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def update(self, *args, **kwds):
        assign(self, *args, kwds)

    def __iter__(self):
        yield from self.__dict__.items()

    def __contains__(self, key):
        return key in self.__fields__ and hasattr(self, key)
            
    def __getitem__(self, key):
        try:
            if self.__allowextra__ or key in self.__fields__:
                return getattr(self, key)
            else:
                raise KeyError(key)
        except AttributeError:
            raise KeyError(key)
        
    def __setitem__(self, key, value):
        if self.__allowextra__ or key in self.__fields__:
            setattr(self, key, value)
        else:
            raise KeyError(key)
    
    def __repr__(self) -> str:
        # fields = ", ".join(f'{f}={getattr(self, f)!r}' for f in sorted(self.__fields__))
        return f'{self.__class__.__name__}({self.target.__name__}, {self.__dict__!r})'



# class metadata(type):

# 	def __new__(mcls, name, bases, dct, **kw):
# 		fields = dct['__type__'] = set()

# 		for k,v in dct.items():
# 			if isinstance(v, metafield):
# 				fields.add(k)
# 				v.__name__ = k

# 		for base in bases:
# 			if isinstance(base, MetadataType):
# 				fields |= base.__fields__

# 		return super(MetadataType, mcls).__new__(mcls, name, bases, dct)

