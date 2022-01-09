from functools import cache, reduce, wraps
import typing as t 
import http

from collections.abc import Iterable
from jani.common.collections import frozendict
from jani.common.enum import IntEnum, StrEnum, auto, Flag

from jani.common.functools import export, cached_class_property


if t.TYPE_CHECKING:
    from .views import View


T_HttpMethodNameLower = t.Literal['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']
T_HttpMethodStr = t.Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE']

T_HttpMethodName = t.Literal[T_HttpMethodNameLower, T_HttpMethodStr]


T_HttpMethods = t.Union[T_HttpMethodName, 'HttpMethod', Iterable[t.Union[T_HttpMethodName, 'HttpMethod']]]

_T_View = t.TypeVar('_T_View', bound='View', covariant=True)


class Route(t.NamedTuple):
    url: str
    name: str
    mapping: dict[T_HttpMethodStr, str]
    detail: bool
    initkwargs: dict[str, t.Any] = frozendict()

    @property
    def key(self):
        return Route, not not self.detail 

class __DynamicRoute(t.NamedTuple):
    url: str
    name: str
    detail: bool
    initkwargs: dict[str, t.Any] = frozendict()


class DynamicRoute(__DynamicRoute):
    __slots__ = ()

    mapping: t.Final = None 

    @property
    def key(self):
        return DynamicRoute, not not self.detail 







def _autostatus(vars: dict):
    for st in http.HTTPStatus:
        val = st._value_, st.phrase, st.description
        vars[f'{st.name}'] = val
        vars[f'{st.name}_{st._value_}'] = val



 

@export()
class ContentShape(StrEnum, fields='is_many'):
    auto: 'ContentShape'    = 'auto', None
    blank: 'ContentShape'   = 'blank', None
    mono: 'ContentShape'    = 'mono', False
    multi: 'ContentShape'   = 'multi', True

    is_many: bool

@export()
class HttpMethod(Flag):

    # ANY: 'HttpMethod'       = auto()

    name: T_HttpMethodStr

    OPTIONS:  'HttpMethod'  = auto() #1 << 1
    HEAD:  'HttpMethod'     = auto() 
    GET:  'HttpMethod'      = auto()
    POST:  'HttpMethod'     = auto()
    PUT:  'HttpMethod'      = auto() 
    PATCH:  'HttpMethod'    = auto() 
    DELETE:  'HttpMethod'   = auto()
    TRACE:  'HttpMethod'    = auto()
    
    options:  'HttpMethod'  = OPTIONS
    head:  'HttpMethod'     = HEAD 
    get:  'HttpMethod'      = GET 
    post:  'HttpMethod'     = POST
    put:  'HttpMethod'      = PUT 
    patch:  'HttpMethod'    = PATCH 
    delete:  'HttpMethod'   = DELETE
    trace:  'HttpMethod'    = TRACE

    @cached_class_property
    def ALL(cls) -> 'HttpMethod':
        return ~cls.TRACE | cls.TRACE
    
    @cached_class_property
    def EXTRA(cls):
        return cls.OPTIONS | cls.TRACE
    
    @cached_class_property
    def STANDALONE(cls):
        return ~cls.EXTRA
    
    @cached_class_property
    def NONE(cls) -> 'HttpMethod':
        return cls(0)
    
    @classmethod
    def _missing_(cls, val):
        tp = val.__class__
        if tp is int:
            return super()._missing_(val)
        elif tp is str:
            mem = cls._member_map_.get(val)
            if mem is None:
                raise ValueError(f"{val!r} is not a valid {cls.__qualname__}")
            return mem
        elif tp in {set, list, tuple}:
            if val:
                return reduce(lambda a, b: a|cls(b), val, cls.NONE)
            return cls.NONE
        
        return super()._missing_(val)
    
    @property
    @cache
    def methods(self) -> tuple['HttpMethod', ...]:
        return *(m for m in self.__class__ if m in self),

    def __contains__(self, x: t.Union['HttpMethod', str]) -> bool:
        if x.__class__ is str:
            if x in self.__class__._member_map_:
                x = self.__class__._member_map_[x]
            elif x.isidentifier():
                return False
        return super().__contains__(x)
    
    def __iter__(self):
        yield from self.methods




@export()
@wraps(http.HTTPStatus, ('__doc__',), ('__annotations__',))
class HttpStatus(IntEnum):

    def __new__(cls, value, phrase, description=''):
        obj = int.__new__(cls, value)
        obj._value_ = value

        obj.phrase = phrase
        obj.description = description
        return obj        
    # __annotations__ = dict(http.HTTPStatus.__annotations__, )

    phrase: str
    description: str
    
    _autostatus(vars())

    if t.TYPE_CHECKING:

    # informational code
        CONTINUE:  'HttpStatus'  = 100 #
        CONTINUE_100:  'HttpStatus'  = CONTINUE #

        SWITCHING_PROTOCOLS:  'HttpStatus'  = 101 #
        SWITCHING_PROTOCOLS_101:  'HttpStatus'  = SWITCHING_PROTOCOLS #

        PROCESSING:  'HttpStatus'  = 102 #
        PROCESSING_102:  'HttpStatus'  = PROCESSING #

        EARLY_HINTS:  'HttpStatus'  = 103 #
        EARLY_HINTS_103:  'HttpStatus'  = EARLY_HINTS #

    # success codes
        OK:  'HttpStatus'  = 200 #
        OK_200:  'HttpStatus'  = OK #

        CREATED:  'HttpStatus'  = 201 #
        CREATED_201:  'HttpStatus'  = CREATED #

        ACCEPTED:  'HttpStatus'  = 202 #
        ACCEPTED_202:  'HttpStatus'  = ACCEPTED #

        NON_AUTHORITATIVE_INFORMATION:  'HttpStatus'  = 203 #
        NON_AUTHORITATIVE_INFORMATION_203:  'HttpStatus'  = NON_AUTHORITATIVE_INFORMATION #

        NO_CONTENT:  'HttpStatus'  = 204 #
        NO_CONTENT_204:  'HttpStatus'  = NO_CONTENT #

        RESET_CONTENT:  'HttpStatus'  = 205 #
        RESET_CONTENT_205:  'HttpStatus'  = RESET_CONTENT #

        PARTIAL_CONTENT:  'HttpStatus'  = 206 #
        PARTIAL_CONTENT_206:  'HttpStatus'  = PARTIAL_CONTENT #

        MULTI_STATUS:  'HttpStatus'  = 207 #
        MULTI_STATUS_207:  'HttpStatus'  = MULTI_STATUS #

        ALREADY_REPORTED:  'HttpStatus'  = 208 #
        ALREADY_REPORTED_208:  'HttpStatus'  = ALREADY_REPORTED #

        IM_USED:  'HttpStatus'  = 226 #
        IM_USED_226:  'HttpStatus'  = IM_USED #

    # redirection codes
        MULTIPLE_CHOICES:  'HttpStatus'  = 300 #
        MULTIPLE_CHOICES_300:  'HttpStatus'  = MULTIPLE_CHOICES #

        MOVED_PERMANENTLY:  'HttpStatus'  = 301 #
        MOVED_PERMANENTLY_301:  'HttpStatus'  = MOVED_PERMANENTLY #

        FOUND:  'HttpStatus'  = 302 #
        FOUND_302:  'HttpStatus'  = FOUND #

        SEE_OTHER:  'HttpStatus'  = 303 #
        SEE_OTHER_303:  'HttpStatus'  = SEE_OTHER #

        NOT_MODIFIED:  'HttpStatus'  = 304 #
        NOT_MODIFIED_304:  'HttpStatus'  = NOT_MODIFIED #

        USE_PROXY:  'HttpStatus'  = 305 #
        USE_PROXY_305:  'HttpStatus'  = USE_PROXY #

        TEMPORARY_REDIRECT:  'HttpStatus'  = 307 #
        TEMPORARY_REDIRECT_307:  'HttpStatus'  = TEMPORARY_REDIRECT #

        PERMANENT_REDIRECT:  'HttpStatus'  = 308 #
        PERMANENT_REDIRECT_308:  'HttpStatus'  = PERMANENT_REDIRECT #

    # client error codes
        BAD_REQUEST:  'HttpStatus'  = 400 #
        BAD_REQUEST_400:  'HttpStatus'  = BAD_REQUEST #

        UNAUTHORIZED:  'HttpStatus'  = 401 #
        UNAUTHORIZED_401:  'HttpStatus'  = UNAUTHORIZED #

        PAYMENT_REQUIRED:  'HttpStatus'  = 402 #
        PAYMENT_REQUIRED_402:  'HttpStatus'  = PAYMENT_REQUIRED #

        FORBIDDEN:  'HttpStatus'  = 403 #
        FORBIDDEN_403:  'HttpStatus'  = FORBIDDEN #

        NOT_FOUND:  'HttpStatus'  = 404 #
        NOT_FOUND_404:  'HttpStatus'  = NOT_FOUND #

        METHOD_NOT_ALLOWED:  'HttpStatus'  = 405 #
        METHOD_NOT_ALLOWED_405:  'HttpStatus'  = METHOD_NOT_ALLOWED #

        NOT_ACCEPTABLE:  'HttpStatus'  = 406 #
        NOT_ACCEPTABLE_406:  'HttpStatus'  = NOT_ACCEPTABLE #

        PROXY_AUTHENTICATION_REQUIRED:  'HttpStatus'  = 407 #
        PROXY_AUTHENTICATION_REQUIRED_407:  'HttpStatus'  = PROXY_AUTHENTICATION_REQUIRED #

        REQUEST_TIMEOUT:  'HttpStatus'  = 408 #
        REQUEST_TIMEOUT_408:  'HttpStatus'  = REQUEST_TIMEOUT #

        CONFLICT:  'HttpStatus'  = 409 #
        CONFLICT_409:  'HttpStatus'  = CONFLICT #

        GONE:  'HttpStatus'  = 410 #
        GONE_410:  'HttpStatus'  = GONE #

        LENGTH_REQUIRED:  'HttpStatus'  = 411 #
        LENGTH_REQUIRED_411:  'HttpStatus'  = LENGTH_REQUIRED #

        PRECONDITION_FAILED:  'HttpStatus'  = 412 #
        PRECONDITION_FAILED_412:  'HttpStatus'  = PRECONDITION_FAILED #

        REQUEST_ENTITY_TOO_LARGE:  'HttpStatus'  = 413 #
        REQUEST_ENTITY_TOO_LARGE_413:  'HttpStatus'  = REQUEST_ENTITY_TOO_LARGE #

        REQUEST_URI_TOO_LONG:  'HttpStatus'  = 414 #
        REQUEST_URI_TOO_LONG_414:  'HttpStatus'  = REQUEST_URI_TOO_LONG #

        UNSUPPORTED_MEDIA_TYPE:  'HttpStatus'  = 415 #
        UNSUPPORTED_MEDIA_TYPE_415:  'HttpStatus'  = UNSUPPORTED_MEDIA_TYPE #

        REQUESTED_RANGE_NOT_SATISFIABLE:  'HttpStatus'  = 416 #
        REQUESTED_RANGE_NOT_SATISFIABLE_416:  'HttpStatus'  = REQUESTED_RANGE_NOT_SATISFIABLE #

        EXPECTATION_FAILED:  'HttpStatus'  = 417 #
        EXPECTATION_FAILED_417:  'HttpStatus'  = EXPECTATION_FAILED #

        IM_A_TEAPOT:  'HttpStatus'  = 418 #
        IM_A_TEAPOT_418:  'HttpStatus'  = IM_A_TEAPOT #

        MISDIRECTED_REQUEST:  'HttpStatus'  = 421 #
        MISDIRECTED_REQUEST_421:  'HttpStatus'  = MISDIRECTED_REQUEST #

        UNPROCESSABLE_ENTITY:  'HttpStatus'  = 422 #
        UNPROCESSABLE_ENTITY_422:  'HttpStatus'  = UNPROCESSABLE_ENTITY #

        LOCKED:  'HttpStatus'  = 423 #
        LOCKED_423:  'HttpStatus'  = LOCKED #

        FAILED_DEPENDENCY:  'HttpStatus'  = 424 #
        FAILED_DEPENDENCY_424:  'HttpStatus'  = FAILED_DEPENDENCY #

        TOO_EARLY:  'HttpStatus'  = 425 #
        TOO_EARLY_425:  'HttpStatus'  = TOO_EARLY #

        UPGRADE_REQUIRED:  'HttpStatus'  = 426 #
        UPGRADE_REQUIRED_426:  'HttpStatus'  = UPGRADE_REQUIRED #

        PRECONDITION_REQUIRED:  'HttpStatus'  = 428 #
        PRECONDITION_REQUIRED_428:  'HttpStatus'  = PRECONDITION_REQUIRED #

        TOO_MANY_REQUESTS:  'HttpStatus'  = 429 #
        TOO_MANY_REQUESTS_429:  'HttpStatus'  = TOO_MANY_REQUESTS #

        REQUEST_HEADER_FIELDS_TOO_LARGE:  'HttpStatus'  = 431 #
        REQUEST_HEADER_FIELDS_TOO_LARGE_431:  'HttpStatus'  = REQUEST_HEADER_FIELDS_TOO_LARGE #

        UNAVAILABLE_FOR_LEGAL_REASONS:  'HttpStatus'  = 451 #
        UNAVAILABLE_FOR_LEGAL_REASONS_451:  'HttpStatus'  = UNAVAILABLE_FOR_LEGAL_REASONS #

    # server errors 
        INTERNAL_SERVER_ERROR:  'HttpStatus'  = 500 #
        INTERNAL_SERVER_ERROR_500:  'HttpStatus'  = INTERNAL_SERVER_ERROR #

        NOT_IMPLEMENTED:  'HttpStatus'  = 501 #
        NOT_IMPLEMENTED_501:  'HttpStatus'  = NOT_IMPLEMENTED #

        BAD_GATEWAY:  'HttpStatus'  = 502 #
        BAD_GATEWAY_502:  'HttpStatus'  = BAD_GATEWAY #

        SERVICE_UNAVAILABLE:  'HttpStatus'  = 503 #
        SERVICE_UNAVAILABLE_503:  'HttpStatus'  = SERVICE_UNAVAILABLE #

        GATEWAY_TIMEOUT:  'HttpStatus'  = 504 #
        GATEWAY_TIMEOUT_504:  'HttpStatus'  = GATEWAY_TIMEOUT #

        HTTP_VERSION_NOT_SUPPORTED:  'HttpStatus'  = 505 #
        HTTP_VERSION_NOT_SUPPORTED_505:  'HttpStatus'  = HTTP_VERSION_NOT_SUPPORTED #

        VARIANT_ALSO_NEGOTIATES:  'HttpStatus'  = 506 #
        VARIANT_ALSO_NEGOTIATES_506:  'HttpStatus'  = VARIANT_ALSO_NEGOTIATES #

        INSUFFICIENT_STORAGE:  'HttpStatus'  = 507 #
        INSUFFICIENT_STORAGE_507:  'HttpStatus'  = INSUFFICIENT_STORAGE #

        LOOP_DETECTED:  'HttpStatus'  = 508 #
        LOOP_DETECTED_508:  'HttpStatus'  = LOOP_DETECTED #

        NOT_EXTENDED:  'HttpStatus'  = 510 #
        NOT_EXTENDED_510:  'HttpStatus'  = NOT_EXTENDED #

        NETWORK_AUTHENTICATION_REQUIRED:  'HttpStatus'  = 511 #
        NETWORK_AUTHENTICATION_REQUIRED_511:  'HttpStatus'  = NETWORK_AUTHENTICATION_REQUIRED #

    def is_informational(self):
        return 100 <= self <= 199

    def is_success(self):
        return 200 <= self <= 299

    def is_redirect(self):
        return 300 <= self <= 399

    def is_client_error(self):
        return 400 <= self <= 499

    def is_server_error(self):
        return 500 <= self <= 599

    def is_error(self):
        return 400 <= self <= 599

