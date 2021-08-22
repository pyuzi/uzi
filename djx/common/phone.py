
from weakref import WeakKeyDictionary
from cachetools import LRUCache, cached
from enum import auto, unique
import typing as t
from cachetools.keys import hashkey
import phonenumbers as base
from phonenumbers import (
    PhoneNumberFormat, PhoneNumberType, NumberParseException,
    CountryCodeSource,

    format_number, format_by_pattern,
    is_valid_number, is_possible_number,
    carrier, is_possible_number_with_reason
)

from djx.di import di

from .collections import fallbackdict
from .enum import IntEnum, StrEnum
from .locale import locale
from .utils import cached_property, text, export

_T_Phone = t.TypeVar('_T_Phone', bound='PhoneNumber', covariant=True)
_T_PhoneStr = t.TypeVar('_T_PhoneStr', bound='PhoneStr', covariant=True)


class CountryCodeSource(IntEnum):
    """The source from which a country code is derived."""
    # Default value returned if this is not set, because the phone number was
    # created using parse(keep_raw_input=False).
    UNSPECIFIED = 0

    # The country_code is derived based on a phone number with a leading "+",
    # e.g. the French number "+33 1 42 68 53 00".
    FROM_NUMBER_WITH_PLUS_SIGN = 1

    # The country_code is derived based on a phone number with a leading IDD,
    # e.g. the French number "011 33 1 42 68 53 00", as it is dialled
    # from US.
    FROM_NUMBER_WITH_IDD = 5

    # The country_code is derived based on a phone number without a leading
    # "+", e.g. the French number "33 1 42 68 53 00" when default_country is
    # supplied as France.
    FROM_NUMBER_WITHOUT_PLUS_SIGN = 10

    # The country_code is derived NOT based on the phone number itself, but
    # from the default_country parameter provided in the parsing function by
    # the clients. This happens mostly for numbers written in the national
    # format (without country code). For example, this would be set when
    # parsing the French number "01 42 68 53 00", when default_country is
    # supplied as France.
    FROM_DEFAULT_COUNTRY = 20



@export()
class PhoneType(IntEnum):

    """Type of phone numbers."""

    FIXED_LINE = 0
    MOBILE = 1
    # In some regions (e.g. the USA), it is impossible to distinguish between
    # fixed-line and mobile numbers by looking at the phone number itself.
    FIXED_LINE_OR_MOBILE = 2
    # Freephone lines
    TOLL_FREE = 3
    PREMIUM_RATE = 4
    # The cost of this call is shared between the caller and the recipient,
    # and is hence typically less than PREMIUM_RATE calls. See
    # http://en.wikipedia.org/wiki/Shared_Cost_Service for more information.
    SHARED_COST = 5
    # Voice over IP numbers. This includes TSoIP (Telephony Service over IP).
    VOIP = 6
    # A personal number is associated with a particular person, and may be
    # routed to either a MOBILE or FIXED_LINE number. Some more information
    # can be found here: http://en.wikipedia.org/wiki/Personal_Numbers
    PERSONAL_NUMBER = 7
    PAGER = 8
    # Used for "Universal Access Numbers" or "Company Numbers". They may be
    # further routed to specific offices, but allow one number to be used for
    # a company.
    UAN = 9
    # Used for "Voice Mail Access Numbers".
    VOICEMAIL = 10
    # A phone number is of type UNKNOWN when it does not fit any of the known
    # patterns for a specific region.
    UNKNOWN = 99

    



class FormatSpec(StrEnum):
    MSISDN          = '%m'
    E164            = '%e'
    LOCAL           = '%l'

    RFC3966         = '%u'
    NATIONAL        = '%n'
    INTERNATIONAL   = '%i'

    CANONICAL       = ''

    @property
    def code(self):
        return self[1:]

    @property
    def type(self):
        return PhoneFormat[self.name]



@export()
@unique
class PhoneFormat(IntEnum):
    E164            = base.PhoneNumberFormat.E164
    INTERNATIONAL   = base.PhoneNumberFormat.INTERNATIONAL
    NATIONAL        = base.PhoneNumberFormat.NATIONAL
    RFC3966         = base.PhoneNumberFormat.RFC3966
    LOCAL           = auto()
    MSISDN          = auto()
    PLAIN           = auto()

    @property
    def spec(self):
        return FormatSpec[self.name]







@export()
class PhoneStr(str):

    __slots__ = ('__phone',)
    __phone: 'PhoneNumber'

    _fmt: t.ClassVar[PhoneFormat] = None

    _cache = WeakKeyDictionary()
    __fmttypes: t.Final[dict[PhoneFormat, type['PhoneStr']]] = dict()

    def __class_getitem__(cls, fmt):
        if isinstance(fmt, tuple):
            assert len(fmt) == 1
            fmt = fmt[0]
        
        if isinstance(fmt, str):
            try:
                fmt = PhoneFormat(fmt)
            except (ValueError, TypeError):
                fmt = PhoneFormat[fmt.upper()]
        elif isinstance(fmt, int):
            fmt = PhoneFormat(fmt)
        else:
            raise TypeError(f'Invalid type {fmt}')
        
        if cls._fmt and cls._fmt != fmt:
            raise TypeError(f'Invalid {cls} format {fmt}')

        if (cls, fmt) not in cls.__fmttypes:
            ftype = type(
                f'{text.camel(fmt.name)}Str', 
                (cls,), 
                dict(_fmt=fmt, _cache=WeakKeyDictionary())
            )
            cls.__fmttypes.setdefault((cls, fmt), ftype)
        return cls.__fmttypes[(cls, fmt)]

    def __new__(cls: type[_T_PhoneStr], phone: t.Union[_T_Phone, 'PhoneStr'], fmt: PhoneFormat=None) -> _T_PhoneStr:
        if cls._fmt is None:
            cls = cls[PhoneFormat.PLAIN if fmt is None else  fmt]
        
        fmt = cls._fmt
        
        if isinstance(phone, PhoneStr):
            return phone.to(fmt)
        
        if fmt is PhoneFormat.PLAIN:
            val = phone.to(PhoneFormat.RFC3966)
        elif fmt is PhoneFormat.MSISDN:
            val = phone.to(PhoneFormat.E164)[1:]
        elif fmt is PhoneFormat.LOCAL:
            if locale.territory == phone.region:
                val = phone.to(PhoneFormat.NATIONAL)
            else:
                val = phone.to(PhoneFormat.INTERNATIONAL)
        # elif not phone.frozen:
        #     val = format_number(phone, fmt)
        elif phone in cls._cache:
            val = cls._cache[phone]
        else:
            val = cls._cache.setdefault(phone, format_number(phone, fmt))

        rv = super().__new__(cls, val)
        rv.__phone = phone
        return rv

    @property
    def phone(self):
        return self.__phone

    def to(self, fmt: PhoneFormat):
        if fmt == self._fmt:
            return self
        else:
            return self.phone.to(fmt)

    @classmethod
    def validate(cls, v, **kwargs):
        if not isinstance(v, cls):
            if isinstance(v, (PhoneStr, PhoneNumber)):
                v = v.to(cls._fmt)
            else:
                v = PhoneNumber.coerce(v, **kwargs).to(cls._fmt)
        
        return v

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def __modify_schema__(cls, field_schema: dict[str, t.Any]) -> None:
        example = to_phone(base.example_number_for_type(locale.territory, PhoneType.MOBILE)).to(cls._fmt)
        field_schema.update(type='string', format=f'phone-number', example=example)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({super().__repr__()})'
    
    def __json__(self):
        return str(self)



@export()
class PhoneNumber(base.PhoneNumber):
    
    Format: t.Final = PhoneFormat

    _frozen: bool = False

    _error_msgs: t.ClassVar[dict[int, str]] = {
        NumberParseException.INVALID_COUNTRY_CODE: '',
        NumberParseException.NOT_A_NUMBER: '',
        NumberParseException.TOO_SHORT_AFTER_IDD: '',
        NumberParseException.TOO_SHORT_NSN: '',
        NumberParseException.TOO_LONG: '',
    }

    _fmt_cls = PhoneStr

    def __init__(self, number: t.Union[str, int, _T_Phone]=None, /, **kwargs):
        
        if isinstance(number, base.PhoneNumber):
            self.__dict__ = number.__dict__.copy()
            kwargs and self.unfreeze()
        else:
            assert number is None or 'country_code' not in kwargs
            kwargs.setdefault('country_code', number)
        
        if not isinstance(number, PhoneNumber):
            self._carriers = dict()
            self._safe_carriers = dict()
        
        kwargs and super().__init__(**kwargs)

    @classmethod
    def parse(cls, number, region=..., *, freeze: bool=True, check_region=True):
        return parse_phone(number, region, freeze=freeze, check_region=check_region, phone_class=cls)

    @property
    def frozen(self):
        return self._frozen

    @cached_property
    def possible(self) -> bool:
        return base.is_possible_number(self)

    @cached_property
    def region(self) -> t.Optional[str]:
        return base.region_code_for_number(self)
        
    @cached_property
    def type(self) -> PhoneType:
        return base.number_type(self)
        
    @cached_property
    def valid(self) -> bool:
        return base.is_valid_number_for_region(self, self.region)

    def carrier(self, *, safe: bool=False) -> t.Optional[str]:
        loc = locale()
        cache = self._safe_carriers if safe is True else self._carriers
        if loc not in cache:
            func = carrier.safe_display_name if safe is True else carrier.name_for_number
            val = func(self, loc.language, loc.script, loc.territory)
            return cache.setdefault(loc, val)
        return cache[loc]
#
    def copy(self):
        return self.__class__(self)
    __copy__ = copy

    def isvalid(self):
        return self.valid

    def isinvalid(self):
        return not self.valid

    def ispossible(self):
        return self.possible

    def isimpossible(self):
        return not self.possible

    def freeze(self):
        self._frozen = True
        return self

    def unfreeze(self):
        self._frozen = False
        return self

    def e164(self):
        return self.to(PhoneFormat.E164)

    def international(self):
        return self.to(PhoneFormat.INTERNATIONAL)
    
    def local(self):
        return self.to(PhoneFormat.LOCAL)

    def msisdn(self):
        return self.to(PhoneFormat.MSISDN)

    def national(self):
        return self.to(PhoneFormat.NATIONAL)

    def plain(self):
        return self.to(PhoneFormat.PLAIN)

    def rfc3966(self):
        return self.to(PhoneFormat.RFC3966)

    def uri(self):
        return self.to(PhoneFormat.RFC3966)

    def to(self, fmt: Format):
        return self._fmt_cls(self, fmt)

    def __len__(self):
        return len(str(self))

    def __hash__(self):
        # if not self.frozen:
        #     raise TypeError(f'{type(self).__name__} must be frozen to be hashable.')
        self.freeze()
        return hash((self.country_code,
                self.national_number,
                self.extension,
                bool(self.italian_leading_zero),
                self.number_of_leading_zeros,
                self.raw_input,
                self.country_code_source,
                self.preferred_domestic_carrier_code))

    def __eq__(self, other):
        if other is self:
            return True
        elif isinstance(other, base.PhoneNumber):
            return super().__eq__(other)
        elif isinstance(other, PhoneStr):
            return self.to(other._fmt) == other
        elif isinstance(other, str):
            return self.plain() == other \
                or self.e164() == other \
                or self.msisdn() == other \
                or self.uri() == other
        else:
            return NotImplemented

    def __setattr__(self, name, value):
        if self._frozen and name != '_frozen':
            raise TypeError(f'{self} is frozen and thus immutable.')
        super().__setattr__(name, value)

    def __delattr__(self, name):
        if self._frozen and name != '_frozen':
            raise TypeError(f'{self} is frozen and thus immutable')
        super().__delattr__(name)

    def __str__(self):
        return self.uri()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.uri()}')"
    
    def __json__(self):
        return self.plain()
#
    @classmethod
    def __get_validators__(cls):
        yield cls.coerce
        # yield cls.check_validity

    @classmethod
    def __modify_schema__(cls, field_schema: dict[str, t.Any]) -> None:
        example = cls(base.example_number_for_type(locale.territory, PhoneType.MOBILE)).international()
        field_schema.update(type='string', format=f'phone-number', example=example)

    @classmethod
    def coerce(cls, v, **kwargs):
        if not isinstance(v, cls):
            try:
                val = to_phone(v, _phone_class=cls)
            except NumberParseException as e:
                raise ValueError(f'must be a valid phone number.') from e
            else:
                field = kwargs.get('field')
                as_valid = getattr(field, 'as_valid', False)
                if not (as_valid or val.isvalid()):
                    raise ValueError(f'must be an valid phone number.')
                return val
        # print(f'xxxxxxxxx coerce {cls} {type(val)=} {val}')
        return v

    # @classmethod
    # def check_validity(cls, val: _T_Phone):
    #     print(f'xxxxxxxxx check_validity {type(val)=} {val!r}')
    #     if val.isinvalid():
    #         raise ValueError(f'must be an valid phone number.')
    #     return val
    
    # @classmethod
    # def check_possibility(cls, val: _T_Phone):
    #     print(f'xxxxxxxxx check_possibility {type(val)=} {val!r}')
    #     if val.isimpossible():
    #         raise ValueError(f'must be an valid phone number.')
    #     return val
    
    


def __cache_key(number, region=..., freeze=True, check_region=True, phone_class=None):
    return hashkey(
        str(number), 
        locale.territory if region is ... else region, 
        freeze,
        check_region, 
        phone_class or PhoneNumber
    )

@cached(LRUCache(2**16), __cache_key)
def parse_phone(number, 
        region: str=..., 
        *, 
        freeze: bool=True, 
        check_region: bool=True, 
        phone_class: type[_T_Phone]=None
) -> _T_Phone: 
    rv = base.parse(
                number,
                # str(number),
                locale.territory if region is ... else region,
                numobj=(phone_class or PhoneNumber)(),
                _check_region=check_region
            )
    # print(f'xxxxxxxxx TYPE {type(rv)} {rv}')
    return rv if freeze is False else rv.freeze()



def to_phone(number: t.Any, *, region: str=..., silent: bool=False, _phone_class: type[_T_Phone]=None) -> _T_Phone:
    if isinstance(number, PhoneStr):
        number = number.phone

    _phone_class = _phone_class or PhoneNumber 
    if isinstance(number, _phone_class):
        return number if number.frozen else number.copy()
    elif isinstance(number, base.PhoneNumber):
        return _phone_class(number)
    
    if isinstance(number, int):
        number = f'+{number}'

    if isinstance(number, str):
        try:
            return parse_phone(number, region, phone_class=_phone_class)    
        except NumberParseException:
            if silent is not True:
                raise
    elif silent is not True:
        raise ValueError(f'must be a valid phone string')
    
        

    