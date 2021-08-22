
import re
import typing as t
from abc import ABCMeta, abstractmethod

from inspect import signature
from functools import partial
from django.db import models as m
# from django.db.models.manager import BaseManager
from djx.common.proxy import proxy


# try:
#     from polymorphic.managers import PolymorphicManager
# except ImportError:
#     PolymorphicManager = None



from collections.abc import Callable

from types import FunctionType
from collections.abc import Callable


from djx.common.utils import cached_property, export
from djx.common.utils.data import DataPath, getitem, setdefault

_T = t.TypeVar('_T')



class AliasExpression:

    __slots__ = 'raw', '__call__'

    def __init__(self, expr: t.Any, static: bool = True) -> None:
        self.raw = expr

        if not isinstance(expr, FunctionType):
            raw = m.F(expr) if isinstance(expr, str) else expr
            def expr(cls):
                return raw

        #     self.__wrapped__ = None
        # else:
        #     self.__wrapped__ = expr

        # self.__signature__ = signature(expr)
        
        # assert len(self.__signature__.parameters) == 1
        # assert next(iter(self.__signature__.parameters), ...) in {'cls', ...}
        
        if static:
            self.__call__ = expr
        else:
            def __call__(cls):
                return proxy(partial(expr, cls))
            self.__call__ = __call__
            




___creation_order_val = 0

def _creation_order():
    global ___creation_order_val
    ___creation_order_val += 1
    return ___creation_order_val



    
@export()
class aliased(cached_property[_T], t.Generic[_T]):

    fget: Callable[[t.Any], _T]

    if t.TYPE_CHECKING:
        def __new__(cls: property[_T], 
                    expr: t.Any=None, 
                    fload: Callable[[t.Any], _T]=None, 
                    fget: Callable[[t.Any], _T]=None, 
                    fset: Callable[[t.Any, t.Any], None]=None, 
                    fdel: Callable[[t.Any], None]=None, 
                    *, name: str=None, 
                    lookup_path: t.Union[str, list]=...,
                    static: bool=None, 
                    annotate: bool=None) -> _T:
            ...

    def __init__(self, 
                expr: t.Any=None, 
                fload: Callable[[t.Any], _T]=None, 
                fget: Callable[[t.Any], _T]=None, 
                fset: Callable[[t.Any, t.Any], None]=None, 
                fdel: Callable[[t.Any], None]=None, 
                *, name: str=None, 
                lookup_path: t.Union[str, list]=...,
                static: bool=None, 
                annotate: bool=None) -> None:
    
        super().__init__(fload, fset, fdel)

        self._order = _creation_order()

        if name is not None:
            self.name = name
        
        if annotate is not None:
            self.annotate = bool(annotate)
        
        if lookup_path is not ...:
            self.lookup_path = lookup_path
        
        self.static = True if static is None else bool(static)
        self.express(expr)
        self.getter(fget)

    @cached_property
    def lookup_path(self) -> DataPath:
        if self.expr is None:
            raise AttributeError('lookup_path: expr not set.')
        
        expr = self.expr.raw
        if isinstance(expr, m.F):
            expr = expr.name
        
        if not isinstance(expr, str):
            return None
    
        ld = len(expr) - len(expr.lstrip('_'))
        rd = len(expr) - len(expr.rstrip('_'))
        return DataPath('_'*ld + expr[ld:-rd].replace('__', '.') + '_'*rd)

    
    @lookup_path.setter
    def lookup_path(self, value):
        self.__dict__['lookup_path'] = value if value is None else DataPath(value)

    @cached_property
    def annotate(self) -> bool:
        return None is self.fget is self.lookup_path

    @property
    def __name__(self):
        return self.attrname

    @cached_property
    def name(self):
        return self.attrname

    def __set_name__(self, owner, name):
        super().__set_name__(owner, name)

        if self.expr is None:
            self.express(self.attrname)

        if self.func is None:
            self.loader(self._load_alias_from_db)
        
        if self.fget is None and self.lookup_path is not None:
            self.getter(self._get_lookup_attr_value)
        
    def __get__(self, obj, typ) -> _T:
        if obj is None:
            return self
        elif self.fget is None:
            return super().__get__(obj, typ)
        else:
            return self.fget(obj)

    def _get_lookup_attr_value(self, obj):
        return getitem(obj, self.lookup_path)

    def _load_alias_from_db(self, obj):
        if obj._state.adding:
            raise AttributeError(f'{self.attrname}')

        hints = {'instance': obj}
        qs = obj.__class__._base_manager\
                .db_manager(obj._state.db, hints=hints)\
                .filter(pk=obj.pk)
        return qs.values_list(self.name, flat=True).first()

    def __call__(self: 'property[_T]', func: Callable[[t.Any], _T]) -> _T:
        self.fget = func
        
        if func:
            self.__doc__ = func.__doc__

        return self

    getter = __call__

    def loader(self, func):
        return super().getter(func)

    def express(self, expr):
        if isinstance(expr, AliasExpression):
            self.expr = AliasExpression(expr.raw, self.static)
        elif expr is not None:
            self.expr = AliasExpression(expr, self.static)
        else:
            self.expr = None

        return self
    
    def contribute_to_class(self, cls: type['Model'], name):
        setattr(cls, name, self)
        self.__set_name__(cls, name)
        cls.__config__.add_aliased_attr(self)

    def __str__(self) -> str:
        return f'{self.__class__.__name__}({self.attrname!r})'
    
    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.attrname!r}, path={self.lookup_path!r})'
        





class SupportsAliasedFields(metaclass=ABCMeta):

    __config__: t.ClassVar['ModelConfig']

    @abstractmethod
    def _supports_aliased_fields_(self) -> 'ModelConfig':
        ...

    @classmethod
    def __subclasshook__(cls, C):
        from .base import ModelConfig
        if cls is SupportsAliasedFields:
            return hasattr(C, '__config__') and isinstance(C.__config__, ModelConfig)
        return NotImplemented





def __del_annotated_attrs(sender, instance: SupportsAliasedFields, created=False, **kwds):
    if not created and isinstance(instance, SupportsAliasedFields):
        for name in instance.__class__.__config__.alias_query_vars:
            delattr(instance, name)

m.signals.post_save.connect(
    __del_annotated_attrs, 
    dispatch_uid=f'{__name__}.__del_annotated_attrs'
)





if t.TYPE_CHECKING:
    from .base import ModelConfig, Model
else:
    ModelConfig = t.Any
    Model = m.Model