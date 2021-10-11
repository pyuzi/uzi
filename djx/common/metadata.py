import re
from abc import ABCMeta

from copy import copy as _copy, deepcopy
import logging
import typing as t

from types import MethodType

from collections import ChainMap
from collections.abc import Mapping, Callable
from threading import RLock

from djx.common.collections import fallbackdict, orderedset
from djx.common.utils import text
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
                        set_final: t.Optional[bool] = False) -> type['BaseMetadata[T]']:
    
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
class metafield(t.Generic[_TF]):
    """Descriptor for meta fields.
    """

    __slots__ = (
        '__name__', '__objclass__', '__weakref__', 'doc', 'field',
        'fload', 'fget', 'fset', 'fdel', '_creation_order',
        'inherit', 'default', 'lock', 'alias'
    )

    def __init__(self, fload=None, field=None, fget=None, fset=None, fdel=None,
                name=None, default=None, inherit=True, doc=None, alias: t.Union[bool, str]=None):
        self.fload = self.fget = self.fset = self.fdel = None

        self.__name__ = name
        self.__objclass__ = None
        self.alias = alias
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

    def __repr__(self):
        attrs = ', '.join(f'{k}={getattr(self, k)!r}' for k in (
            'field', 'alias', 'inherit'
        ))
        return f"{self.__class__.__name__}({self.__name__!r}, {attrs})" 

    def __getstate__(self):
        return { k: getattr(self, k) for k in (
            '__name__', 'doc', 'field',
            'fload', 'fget', 'fset', 'fdel',
            'inherit', 'default', 'alias'
        )}

    def __setstate__(self, state):
        keys = {'__name__', 'doc', 'field',
                            'fload', 'fget', 'fset', 'fdel',
                            'inherit', 'default', 'alias'}
        for k in state.keys() & keys:
            setattr(self, k, state[k])
        self.__objclass__ = None
        self._creation_order = _get_creation_order()
        self.lock = RLock()

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
            return self

        raise TypeError('Expected callable or None. Got %s.' % type(func))

    def setter(self, func):
        if func is None or callable(func):
            self.fset = func
            return self
        raise TypeError('Expected callable or None. Got %s.' % type(func))

    def deletter(self, func):
        if func is None or callable(func):
            self.fdel = func
            return self
        raise TypeError('Expected callable or None. Got %s.' % type(func))

    def contribute_to_class(self, owner, name=None):
        assert (name is None or self.__name__ is None) or self.__name__ == name, (
                f'attribute __name__ must be set to bind {type(self)}'
            )

        if self.__objclass__:
            assert issubclass(owner, self.__objclass__), (
                f'can only contribute to subclasses of {self.__objclass__}. {owner} given.'
            )
        
        if name:
            setattr(owner, name, self)
            self.__set_name__(owner, name)

    def __set_name__(self, owner, name):
        if self.__objclass__ is None:
            self.__objclass__ = owner
            self.__name__ = name
        elif self.__objclass__ is owner:
            self.__name__ = name
        else:
            raise RuntimeError(f'__set_name__. metafield already bound.')
        
        if not self.field:
            self.field = name
            
        if self.alias is True:
            if self.field == name:
                self.alias = False
            else:
                self.alias = name
        elif self.alias == self.field:
            self.alias = False

    def __call__(self, fload: t.Callable[..., _TF]) -> 'metafield[_TF]':
        assert self.fload is None, ('metafield option already has a loader.')
        self.loader(fload)
        return self

    def __load__(self, obj) -> t.Union[_TF, t.Any]:
        try:
            # rv = obj.__raw__[self.field or self.__name__]
            rv = obj.__raw__[self.field]
        except KeyError:
            if self.alias:
                rv = obj.__raw__.get(self.alias, Void)
            else:
                rv = Void
        except AttributeError:
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

            if self.fset is not None:
                self.fset(obj, rv)
                rv = NotImplemented
        else:
            if not self.inherit or base is None:
                args = ()
            else:
                try:
                    args = base[self.__name__],
                except KeyError:
                    args = ()

            rv = self.fload(obj, self.default if rv is Void else rv, *args)
        
        if rv is not NotImplemented:
            obj.__dict__[self.__name__] = rv
        
        obj.__fieldset__.add(self.__name__)

        return rv


    def __get__(self, obj: 'BaseMetadata', cls) -> _TF:
        if obj is None:
            return self

        fget = self.fget
        if self.__name__ in obj.__fieldset__:
            if fget is not None:
                return fget(obj)
            else:
                try:
                    return obj.__dict__[self.__name__]
                except KeyError:
                    raise AttributeError(self.__name__)

        with self.lock:
            
            rv = self.__load__(obj)
            
            if fget is None:
                if rv is NotImplemented:
                    raise AttributeError(self.__name__)
                
                return rv

            return fget(obj)

            # return rv if self.fget is None else self.fget(obj, rv)
            # return rv if self.fget is None else self.fget(obj)

    def __set__(self, obj, value):
        with self.lock:
            if self.__name__ not in obj.__fieldset__:
                self.__load__(obj)
            
            if self.fset is not None:
                # obj.__dict__[self.__name__] = self.fset(obj, value)
                self.fset(obj, value)
            elif self.fload is not None:
                if self.inherit:
                    val = self.fload(obj, value, obj.__dict__.get(self.__name__))
                else:
                    val = self.fload(obj, value)
                
                if val is not NotImplemented:
                    obj.__dict__[self.__name__] = val
            else:
                obj.__dict__[self.__name__] = value

            # obj.__fieldset__.add(self.__name__)


    def __delete__(self, obj):
        if self.fdel is not None:
            self.fdel(obj)
        obj.__dict__.pop(self.__name__, None)
        obj.__fieldset__.discard(self.__name__)


if t.TYPE_CHECKING:
    
    class metafield(property[_TF], metafield[_TF], t.Generic[_TF]):
        
        def __get__(self, obj, cls) -> _TF:
            ...

class MetadataType(ABCMeta):

    __fields__: orderedset
    __fieldaliases__: fallbackdict
    __fieldset__: orderedset[str]

    def __new__(mcls, name, bases, dct):
        cls = super().__new__(mcls, name, bases, dct)
        cls.register_metafields()

        # debug(f'{cls.__module__}:{cls.__qualname__}', {f: getattr(cls, f) for f in cls.__fields__})
        return cls

    def register_metafields(self):
        self.__fields__= fieldset = orderedset()
        self.__fieldaliases__ = aliases = fallbackdict(lambda k: k)
        for name, field in self._iter_metafields():
            field.contribute_to_class(self, name)
            fieldset.add(name)
            # field.field and fieldset.add(field.field)
            if field.alias:
                aliases[field.alias] = name
        
    def _iter_metafields(self):
        seen = set(self.__dict__)
        for b in reversed(self.mro()[1:]):
            for n in b.__fields__ if isinstance(b, MetadataType) else dir(b):
                if n not in seen:
                    f = getattr(self, n, None)
                    if isinstance(f, metafield):
                        seen.add(n)
                        yield n, deepcopy(f)

        for n in self.__dict__:
            f = getattr(self, n)
            if isinstance(f, metafield):
                yield n, f


        # fields = (
        #     (k,v) for b in self.mro()
        #         for k in b.__dict__
        #             if isinstance(v := getattr(self, k, None), metafield)
        # )

        # return fields
        # mro.append(None)
        # yield from sorted(fields, key=lambda kv: (mro.index(kv[1].__objclass__)+1, kv[1]._creation_order))

        





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

    # __slots__ =(
    #     '__name__', '__raw__', '__base__', 'target', '__allowextra__',
    #     '__dict__', '__weakref__'
    # )
    __fields__: orderedset
    __fieldaliases__: dict[str, str]

    __name__: str
    __allowextra__: t.ClassVar[bool] = False

    target: t.Type[T]

    def __init__(self, target = None, name=None, raw=None, base=None, *, allowextra=None):
        self.target = None

        self.__fieldset__ = set()

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
        fieldset = self.__fieldset__
        fieldset.clear()

        for f in self.__fields__:
            getattr(self, f, None)

        if self.__allowextra__:
            skip = set(dir(self)) | fieldset | self.__fields__ | self.__fieldaliases__.keys()
            for k in self.__raw__.keys() - skip:
                if isinstance(k, str) and k[0] != '_':
                    fieldset.add(k)
                    setattr(self, k, self.__raw__[k])

            for k in self.__base__.keys() - (skip | fieldset):
                if isinstance(k, str) and k[0] != '_':
                    fieldset.add(k)
                    setattr(self, k, self.__base__[k])

        self.__loaded__()
        del self.__raw__
        del self.__base__
        self.__ready__()

    def __loaded__(self):
        pass

    def __ready__(self):
        pass

    def copy(self, **replace):
        if not self._metadataloaded_:
            raise RuntimeError(f'{self.__class__.__name__} not loaded')
        rv = _copy(self)
        replace and rv.__dict__.update(replace)
        return rv

    def __getstate__(self):
        if not self._metadataloaded_:
            raise RuntimeError(f'{self.__class__.__name__} not loaded')
        return self.__dict__.copy()
        
    def __setstate__(self, val):
        self.__dict__.update(val)
    
    def __getattr__(self, alias):
        name = self.__fieldaliases__[alias]
        if name is alias:
            # return NotImplemented
            raise AttributeError(alias)
        
        return getattr(self, name)

    @classmethod
    def _base_from_target(cls, target, attr):
        if isinstance(target, type):
            maps = (getattr(b, attr, None) for b in target.__bases__)
            maps = (b for b in maps if isinstance(b, BaseMetadata))
            return ChainMap({}, *maps)
        return getattr(target.__class__, attr, {})

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
        
    def update(self, *args, **kwds):
        assign(self, *args, kwds)

    def __iter__(self):
        yield from self.__dict__

    def __contains__(self, key):
        # return self.__fieldset__.__contains__(key) and hasattr(self, key)
        return isinstance(key, str) and hasattr(self, key)
            
    def __getitem__(self, key):
        # if isinstance(key, str):
            # if True or not text.is_dunder(key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError()
        
    def __setitem__(self, key, value):
        setattr(self, key, value)
    
    # def __repr__(self) -> str:
    #     # attrs = dict((k, self.__dict__[k]) for k in self.__dict__ if not text.is_dunder(k))
    #     print(self.__fieldset__)
    #     attrs = { k : self.get(k, ...) for k in self.__fieldset__ }
    #     return f'{self.__class__.__name__}({self.target.__name__}, {attrs})'
    
    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.target})'

