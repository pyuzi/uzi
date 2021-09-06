import typing as t
from string import Formatter
from collections.abc import Sequence, Mapping

from djx.common.collections import fallbackdict
from djx.common.utils import export, class_property, cached_class_property, text


from cachetools.keys import hashkey

try:
    from django.core.exceptions import ImproperlyConfigured as _BaseImproperlyConfigured
except ImportError:
    _BaseImproperlyConfigured = Exception


class ImproperlyConfigured(_BaseImproperlyConfigured):
    """Your app is somehow improperly configured"""
    ...


class ErrorFormatter(Formatter):

    def get_value(self, key: t.Union[int, str], args: Sequence[t.Any], kwds: Mapping[str, t.Any]) -> t.Any:
        if isinstance(key, str):
            try:
                return kwds[key]
            except KeyError:
                return key
        else:
            return super().get_value(key, args, kwds)



class BaseError(Exception):
    ctx: dict[str, t.Any]

    error_type: str = None
    http_status_code: int
    msg_template: t.ClassVar[str]

    formatter: t.ClassVar[Formatter] = ErrorFormatter()
    
    base_loc: t.ClassVar[tuple[t.Any]] = ()
    default_loc: t.ClassVar[tuple[t.Any]] = None
    default_ctx: t.ClassVar[dict[str, t.Any]] = None
    
    def __init__(self, msg: t.Any = None, *loc: t.Any, **ctx: t.Any) -> None:
        if msg is not None:
            self.msg_template = msg
        self.loc = self.base_loc + (loc or self.default_loc or ())
        self.ctx = fallbackdict(self.default_ctx, ctx)

    @cached_class_property
    def type(cls):
        return cls.error_type or text.snake(cls.__name__)

    @property
    def msg(self):
        return str(self)

    def dict(self, *loc: t.Any):
        data = dict(
            loc=(loc + self.loc) or None,
            msg=self.msg,
            type=self.type,
            ctx=self.ctx or None
        )
        return {k:v for k,v in data.items() if v is not None}
        
    def __getattr__(self, name):
        if name not in {'ctx', 'loc', 'msg_template'}:
            try:
                return self.ctx[name]
            except KeyError:
                pass
        raise AttributeError(name)

    def __str__(self) -> str:
        return self.formatter.format(self.msg_template, **self.ctx)

    def __repr__(self):
        return f'{self.__class__.__name__}({self.dict()})'

    def __eq__(self, other):
        if not isinstance(other, BaseError):
            return NotImplemented
        return hash(self) == hash(other)

    def __hash__(self):
        return hashkey(self.msg_template, *self.loc, **self.ctx)
    


@export()
class ValidationError(BaseError):
    
    error_type = 'value_error'
    msg_template = 'invalid value.'



@export()
class DataError(BaseError):
    
    default_loc = ('data',)


@export()
class DataTypeError(DataError, TypeError):
    
    error_type = 'type_error'

    
@export()
class DataValueError(DataError, ValueError):
    
    error_type = 'value_error'

    

@export()
class OperationError(BaseError, RuntimeError):
    status_code = 400
    msg_template = 'error performing task.'
    
    
    

@export()
class ResourceError(BaseError):
    default_loc = ('resource',)
    # code = 'resource_error'




@export()
class DoesNotExistError(ResourceError):
    http_status_code = 400
    msg_template = '{resource} does not exist.'



@export()
class NotFoundError(ResourceError):
    http_status_code = 404
    msg_template = '{resource} not found.'
    
    