import re
import typing as t 
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
    _BaseAddress,
    _BaseNetwork,
)

from collections.abc import Callable
from jani.common.collections import fallbackdict, frozendict

from pydantic import errors, validate_email
from pydantic.validators import constr_length_validator, str_validator

from jani.common.utils import export
from jani.common.proxy import unproxy
from jani.common.paths import UriPathStr



if t.TYPE_CHECKING:
    from pydantic.fields import ModelField
    from pydantic.main import BaseConfig  # noqa: F401

    CallableGenerator = t.Generator[Callable[..., t.Any], None, None]
else:
    __all__ = [
        'AnyUrl',
        'AnyHttpUrl',
        'HttpUrl',
        'stricturl',
        'IPvAnyAddress',
        'IPvAnyInterface',
        'IPvAnyNetwork',
        'PostgresDsn',
        'RedisDsn',
    ]

NetworkType = t.Union[str, bytes, int, tuple[t.Union[str, bytes, int], t.Union[str, int]]]

HostType = t.Literal['domain', 'int_domain', 'ipv4', 'ipv6']


_url_regex_cache = None
_ascii_domain_regex_cache = None
_int_domain_regex_cache = None

_T_Url = t.TypeVar('_T_Url', bound='AnyUrl', covariant=True)



def url_regex() -> re.Pattern[str]:
    global _url_regex_cache
    if _url_regex_cache is None:
        _url_regex_cache = re.compile(
            r'(?:(?P<scheme>[a-z][a-z0-9+\-.]+)://)?'  # scheme https://tools.ietf.org/html/rfc3986#appendix-A
            r'(?:(?P<user>[^\s:/]*)(?::(?P<password>[^\s/]*))?@)?'  # user info
            r'(?:'
            r'(?P<ipv4>(?:\d{1,3}\.){3}\d{1,3})|'  # ipv4
            r'(?P<ipv6>\[[A-F0-9]*:[A-F0-9:]+\])|'  # ipv6
            r'(?P<domain>[^\s/:?#]+)'  # domain, validation occurs later
            r')?'
            r'(?::(?P<port>\d+))?'  # port
            r'(?P<path>/[^\s?#]*)?'  # path
            r'(?:\?(?P<query>[^\s#]+))?'  # query
            r'(?:#(?P<fragment>\S+))?',  # fragment
            re.IGNORECASE,
        )
    return _url_regex_cache


def ascii_domain_regex() -> re.Pattern[str]:
    global _ascii_domain_regex_cache
    if _ascii_domain_regex_cache is None:
        ascii_chunk = r'[_0-9a-z](?:[-_0-9a-z]{0,61}[_0-9a-z])?'
        ascii_domain_ending = r'(?P<tld>\.[a-z]{2,63})?\.?'
        _ascii_domain_regex_cache = re.compile(
            fr'(?:{ascii_chunk}\.)*?{ascii_chunk}{ascii_domain_ending}', re.IGNORECASE
        )
    return _ascii_domain_regex_cache


def int_domain_regex() -> re.Pattern[str]:
    global _int_domain_regex_cache
    if _int_domain_regex_cache is None:
        int_chunk = r'[_0-9a-\U00040000](?:[-_0-9a-\U00040000]{0,61}[_0-9a-\U00040000])?'
        int_domain_ending = r'(?P<tld>(\.[^\W\d_]{2,63})|(\.(?:xn--)[_0-9a-z-]{2,63}))?\.?'
        _int_domain_regex_cache = re.compile(fr'(?:{int_chunk}\.)*?{int_chunk}{int_domain_ending}', re.IGNORECASE)
    return _int_domain_regex_cache




@export()
class EmailStr(str):

    __slots__ = '_name',

    _name: str
    _implicit: bool = True

    def __new__(cls, name: str, email: str = None):

        if email is None:
            email = name
            name = email[:email.index('@')]

        rv = super().__new__(cls, email)
        rv._name = name
        
        return rv

    @property
    def name(self):
        return self._name

    @property
    def email(self):
        return str(self)

    def __reduce__(self):
        return self.__class__, (self.name, self.email)

    @classmethod
    def __modify_schema__(cls, field_schema) -> None:
        field_schema.update(type='string', format='email')

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, **kwargs) -> 'NameEmail':
        if v.__class__ is cls:
            return unproxy(v)

        v = str_validator(v)
        # if kwargs:
        #     v = constr_length_validator(v, kwargs.get('field'), kwargs.get('config'))

        return cls(*validate_email(v))

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({str(self)!r})'



@export()
class NameEmailStr(EmailStr):

    __slots__ =  '_email', '_implicit'
    _implicit: bool

    def __new__(cls, name: str, email: str):
        rv = super().__new__(cls, name, f'{name} <{email}>')
        rv._email = email
        rv._implicit = name == email[:email.index('@')] 

        return rv

    @property
    def email(self):
        return self._email

    @classmethod
    def __modify_schema__(cls, field_schema) -> None:
        field_schema.update(type='string', format='name-email')

    def __eq__(self, x) -> bool:
        if isinstance(x, EmailStr):
            return self.email == x.email \
                and (True is self._implicit is x._implicit or self.name == x.name)
        elif isinstance(x, str):
            return self._implicit and x == self._email

        return super().__eq__(x)

    def __ne__(self, x) -> bool:
        return not (self == x)



@export()
class NameEmail:

    __slots__ = 'name', 'email',


    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email

    __repr__ = NameEmailStr.__repr__
    __reduce__ = NameEmailStr.__reduce__
    __get_validators__ = NameEmailStr.__get_validators__
    __modify_schema__ = NameEmailStr.__modify_schema__
    validate = NameEmailStr.validate

    def __eq__(self, other) -> bool:
        if isinstance(other, (NameEmail, EmailStr)):
            return self.email == other.email and self.name == other.name
        return NotImplemented

    def __hash__(self):
        return hash((self.name, self.email))

    def __str__(self) -> str:
        return f'{self.name} <{self.email}>'



def url_part_getter(n: str):
    def getter(self: 'AnyUrl'):
        nonlocal n
        try:
            return self._parts[n]
        except AttributeError:
            self._init_parts()
            return getter(self)
        except KeyError:
            raise AttributeError(n)
    getter.__name__ = n
    return getter



if t.TYPE_CHECKING:
    class PartsDict(t.TypedDict, total=False):

        scheme: t.Optional[str]
        user: t.Optional[str] 
        password: t.Optional[str] 
        hostname: t.Optional[str] 
        tld: t.Optional[str] 
        host_type: t.Optional[HostType]
        port: t.Optional[str]
        path: t.Optional[UriPathStr]
        query: t.Optional[str]
        fragment: t.Optional[str]

else:
    class PartsDict(frozendict):

        def __missing__(self, k):
            return None


class _PartsPropertyMixin:
    
    __slots__ = ()

    PARTS = ()

    def __init_subclass__(cls) -> None:
        for n in cls.PARTS:
            if not hasattr(cls, n):
                setattr(cls, n, property(url_part_getter(n)))


@export()
class AnyUrl(str, _PartsPropertyMixin):
    strip_whitespace = True
    min_length = 1
    max_length = 2 ** 16
    allowed_schemes: t.Optional[set[str]] = None
    tld_required: bool = False
    user_required: bool = False

    __slots__ = '_parts',

    PARTS = ('scheme', 'user', 'password', 'hostname', 'tld', 'host_type', 'port', 'path', 'query', 'fragment')
    PARTS_DICT_CLASS: type[PartsDict] = PartsDict
    PATH_CLASS: type[UriPathStr] = UriPathStr
    MISSING_PART = ''

    _parts: PartsDict

    scheme: t.Optional[str]
    user: t.Optional[str] 
    password: t.Optional[str] 
    hostname: t.Optional[str] 
    tld: t.Optional[str] 
    host_type: t.Optional[HostType]
    port: t.Optional[str]
    path: t.Optional[UriPathStr]
    query: t.Optional[str]
    fragment: t.Optional[str]

    @t.no_type_check
    def __new__(cls, url: t.Optional[str]=None, /, **kwds) -> object:
        if url is None:
            if not kwds:
                raise TypeError(f'positional or keyword arguments must be provied.')
            self = str.__new__(cls, cls.build(**kwds))
            self._init_parts(kwds)
            return self
        elif kwds:
            raise TypeError(f'positional or keyword arguments are mutually exclusive')
        elif url.__class__ is cls:
            return t.cast(cls, url)

        return str.__new__(cls, url)

    if t.TYPE_CHECKING:
        def __init__(
            self,
            url: str,
            *,
            scheme: str,
            user: t.Optional[str] = None,
            password: t.Optional[str] = None,
            hostname: str,
            tld: t.Optional[str] = None,
            host_type: str = 'domain',
            port: t.Optional[str] = None,
            path: t.Optional[str] = None,
            query: t.Optional[str] = None,
            fragment: t.Optional[str] = None,
        ) -> None:
            ...

    @property
    def credentials(self):
        cred = ''
        if user := self.user:
            cred = user
        if passw := self.password:
            cred += f':{passw}'
        return cred or self.MISSING_PART
         
    @property
    def host(self):
        if host := self.hostname:
            if port := self.port:
                return f'{host}:{port}'
        return host
         
    @property
    def netloc(self):
        if host := self.host:
            if cred := self.credentials:
                cred += '@'
            return f'{cred}{host}'
        return self.MISSING_PART
     
    @property
    def origin(self):
        return self.__class__(
                scheme=self.scheme, 
                user=self.user, 
                password=self.password, 
                hostname=self.hostname, 
                port=self.port
            )
         
    @property
    def parts(self) -> PartsDict:
        try:
            return self._parts
        except AttributeError:
            return self._init_parts()

    def _init_parts(self, parts: t.Optional[dict[str, t.Any]]=None) -> PartsDict:
        if hasattr(self, '_parts'):
            if parts is None:
                return self._parts
            raise AttributeError(f'parts already set.')

        if parts is None:
            u, parts = self._parse_str(self)
            if u != self:
                raise ValueError(
                    f'invalid encoding. Ensure url is only made up of ASCII characters. '
                    f'or use {self.__class__.__name__}.parse({str(self)!r}).'
                )
        self._parts = self.PARTS_DICT_CLASS(parts)
        return self._parts            

    @t.overload
    def replace(
        self: _T_Url,
        *,
        scheme: str,
        user: t.Optional[str] = None,
        password: t.Optional[str] = None,
        hostname: str,
        port: t.Optional[str] = None,
        path: t.Optional[str] = None,
        query: t.Optional[str] = None,
        fragment: t.Optional[str] = None,
        **kwargs: str,
    ) -> _T_Url:
        ...
    def replace(self, **kwds):
        if kwds:
            return self.__class__(**(self.parts | kwds))
        return self

    def __reduce__(self):
        return self._from_parsed_attrs, (str(self), self.parts) 

    @classmethod
    def build(
        cls,
        *,
        scheme: str,
        user: t.Optional[str] = None,
        password: t.Optional[str] = None,
        hostname: str,
        port: t.Optional[str] = None,
        path: t.Optional[str] = None,
        query: t.Optional[str] = None,
        fragment: t.Optional[str] = None,
        **kwargs: str,
    ) -> str:
        url = ''
        if scheme:
            url = scheme + '://'
        if user:
            url += user
        if password:
            url += ':' + password
        if user or password:
            url += '@'
        if hostname:
            url += hostname
        if port:
            url += ':' + port
        if path:
            url += path
        if query:
            url += '?' + query
        if fragment:
            url += '#' + fragment
        return url


    @classmethod
    def _from_parsed_attrs(cls, url: str, parts: PartsDict):
        obj = cls(url)
        obj._init_parts(parts)
        return obj

    @classmethod
    def parse(cls, value: t.Any, *, strict: bool=False):
        if value.__class__ is cls:
            return t.cast(cls, unproxy(value))

        url, parts = cls._parse_str(str(value), strict=strict)
        obj = cls(cls.build(**parts) if url is None else url)
        obj._init_parts(parts)
        return obj

    @classmethod
    def _parse_str(cls, url: str, *, strict: bool=False) -> tuple[t.Optional[str], PartsDict]:
    
        m = url_regex().match(url)
        # the regex should always match, if it doesn't please report with details of the URL tried
        assert m, 'URL regex failed unexpectedly'

        parts = m.groupdict(cls.MISSING_PART)
        parts = cls._parse_parts(parts, strict=strict)

        hostname, tld, host_type, rebuild = cls._parse_host(parts, strict=strict)

        if strict and m.end() != len(url):
            raise errors.UrlExtraError(extra=url[m.end() :])

        return None if rebuild else url, dict(
            scheme=parts['scheme'],
            user=parts['user'],
            password=parts['password'],
            hostname=hostname,
            tld=tld,
            host_type=host_type,
            port=parts['port'],
            path=parts['path'],
            query=parts['query'],
            fragment=parts['fragment'],
        )

    @classmethod
    def _parse_parts(cls, parts: PartsDict, *, strict: bool=False) -> dict[str, str]:
        """
        A method used to validate parts of an URL.
        Could be overridden to set default values for parts if missing
        """
        scheme = parts['scheme']
        missing = cls.MISSING_PART

        if strict:
            if scheme is missing:
                raise errors.UrlSchemeError()
            elif cls.allowed_schemes and scheme.lower() not in cls.allowed_schemes:
                raise errors.UrlSchemePermittedError(cls.allowed_schemes)

            port = parts['port']
            if port is not missing and int(port) > 65_535:
                raise errors.UrlPortError()

            user = parts['user']
            if cls.user_required and user is missing:
                raise errors.UrlUserInfoError()

        elif scheme and cls.allowed_schemes and scheme.lower() not in cls.allowed_schemes:
            raise errors.UrlSchemePermittedError(cls.allowed_schemes)

        path = parts['path']
        if path is not None:
            parts['path'] = cls.PATH_CLASS(path)
        
        return parts

    @classmethod
    def _parse_host(cls, parts: dict[str, str], *, strict: bool=False) -> tuple[str, t.Optional[str], str, bool]:
        missing = cls.MISSING_PART
        
        hostname, tld, host_type, rebuild = missing, None, None, False
        for f in ('domain', 'ipv4', 'ipv6'):
            hostname = parts[f]
            if hostname:
                host_type = f
                break

        if hostname is missing:
            raise errors.UrlHostError()
        elif host_type == 'domain':
            is_international = False
            d = ascii_domain_regex().fullmatch(hostname)
            if d is None:
                d = int_domain_regex().fullmatch(hostname)
                if d is None:
                    raise errors.UrlHostError()
                is_international = True

            tld = d.group('tld')
            if tld is None and not is_international:
                d = int_domain_regex().fullmatch(hostname)
                tld = d.group('tld')
                is_international = True

            if tld is not None:
                tld = tld[1:]
            elif cls.tld_required:
                raise errors.UrlHostTldError()

            if is_international:
                host_type = 'int_domain'
                rebuild = True
                hostname = hostname.encode('idna').decode('ascii')
                if tld is not None:
                    tld = tld.encode('idna').decode('ascii')

        return hostname.lower(), tld, host_type, rebuild  # type: ignore

    @classmethod
    def __modify_schema__(cls, field_schema: dict[str, t.Any]) -> None:
        items = [('minLength', cls.min_length), ('maxLength', cls.max_length)]
        field_schema.update((kv for kv in items  if kv[1] is not None), format='uri')

    @classmethod
    def __get_validators__(cls) -> 'CallableGenerator':
        yield cls.validate

    @classmethod
    def validate(cls, value: t.Any, field: 'ModelField', config: 'BaseConfig') -> 'AnyUrl':
        if value.__class__ is cls:
            return unproxy(value)
            
        value = str_validator(value)
        if cls.strip_whitespace:
            value = value.strip()
        url: str = t.cast(str, constr_length_validator(value, field, config))
        return cls.parse(url, strict=True)

    def __repr__(self) -> str:
        extra = ', '.join(f'{n}={getattr(self, n)!r}' for n in self.__slots__ if getattr(self, n) is not None)
        extra = extra and f', {extra}'
        return f'{self.__class__.__name__}({super().__repr__()}{extra})'




@export()
class AnyHttpUrl(AnyUrl):
    __slots__ = ()
    allowed_schemes = {'http', 'https'}


@export()
class HttpUrl(AnyHttpUrl):
    __slots__ = ()

    allowed_schemes = {'http', 'https'}
    tld_required = True
    # https://stackoverflow.com/questions/417142/what-is-the-maximum-length-of-a-url-in-different-browsers
    max_length = 2083


@export()
class PostgresDsn(AnyUrl):
    __slots__ = ()
    allowed_schemes = {'postgres', 'postgresql'}
    user_required = True


@export()
class RedisDsn(AnyUrl):
    __slots__ = ()
    allowed_schemes = {'redis', 'rediss'}

    @classmethod
    def validate_parts(cls, parts: dict[str, str]) -> dict[str, str]:
        defaults = {
            'domain': 'localhost' if not (parts['ipv4'] or parts['ipv6']) else '',
            'port': '6379',
            'path': '/0',
        }
        for key, value in defaults.items():
            if not parts[key]:
                parts[key] = value
        return super()._parse_parts(parts)



@t.overload
def stricturl(
    type_: type[_T_Url]=AnyUrl, 
    /,
    *,
    strip_whitespace: bool = True,
    min_length: int = 1,
    max_length: int = 2 ** 16,
    tld_required: bool = True,
    allowed_schemes: t.Optional[t.Union[frozenset[str], set[str]]] = None,
    **kwds
) -> type[_T_Url]:
    ...

@export()
def stricturl(type_: type[_T_Url]=AnyUrl, /, **namespace) -> type[_T_Url]:
    # use kwargs then define conf in a dict to aid with IDE type hinting
    namespace['__slots__'] = ()
    return type('UrlValue', (type_,), namespace)



@export()
class IPvAnyAddress(_BaseAddress):
    @classmethod
    def __modify_schema__(cls, field_schema: dict[str, t.Any]) -> None:
        field_schema.update(type='string', format='ipvanyaddress')

    @classmethod
    def __get_validators__(cls) -> 'CallableGenerator':
        yield cls.validate

    @classmethod
    def validate(cls, value: t.Union[str, bytes, int]) -> t.Union[IPv4Address, IPv6Address]:
        try:
            return IPv4Address(value)
        except ValueError:
            pass

        try:
            return IPv6Address(value)
        except ValueError:
            raise errors.IPvAnyAddressError()


@export()
class IPvAnyInterface(_BaseAddress):
    @classmethod
    def __modify_schema__(cls, field_schema: dict[str, t.Any]) -> None:
        field_schema.update(type='string', format='ipvanyinterface')

    @classmethod
    def __get_validators__(cls) -> 'CallableGenerator':
        yield cls.validate

    @classmethod
    def validate(cls, value: NetworkType) -> t.Union[IPv4Interface, IPv6Interface]:
        try:
            return IPv4Interface(value)
        except ValueError:
            pass

        try:
            return IPv6Interface(value)
        except ValueError:
            raise errors.IPvAnyInterfaceError()


@export()
class IPvAnyNetwork(_BaseNetwork):  # type: ignore
    @classmethod
    def __modify_schema__(cls, field_schema: dict[str, t.Any]) -> None:
        field_schema.update(type='string', format='ipvanynetwork')

    @classmethod
    def __get_validators__(cls) -> 'CallableGenerator':
        yield cls.validate

    @classmethod
    def validate(cls, value: NetworkType) -> t.Union[IPv4Network, IPv6Network]:
        # Assume IP Network is defined with a default value for ``strict`` argument.
        # Define your own class if you want to specify network address check strictness.
        try:
            return IPv4Network(value)
        except ValueError:
            pass

        try:
            return IPv6Network(value)
        except ValueError:
            raise errors.IPvAnyNetworkError()


pretty_email_regex = re.compile(r'([\w ]*?) *<(.*)> *')
