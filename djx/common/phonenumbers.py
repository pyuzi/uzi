import typing as t
import phonenumbers
from phonenumbers import (
    PhoneNumberFormat, PhoneNumberType, NumberParseException,
    PhoneNumber as BasePhoneNumber, CountryCodeSource,

    format_number, format_by_pattern,
    is_valid_number, is_possible_number,
    carrier, is_possible_number_with_reason
)


class PhoneNumber(BasePhoneNumber):


    _error_msgs: t.ClassVar[dict[int, str]] = {
        NumberParseException.INVALID_COUNTRY_CODE: '',
        NumberParseException.NOT_A_NUMBER: '',
        NumberParseException.TOO_SHORT_AFTER_IDD: '',
        NumberParseException.TOO_SHORT_NSN: '',
        NumberParseException.TOO_LONG: '',
    }


    def __init__(self, country_code=None, national_number=None, **kwargs):
        super().__init__(
                country_code=country_code,
                national_number=national_number,
                **kwargs
            )

        self.raw = None

    @property
    def raw(self) -> str:
        rv = self.__dict__['raw']
        if rv is None:
            rv = self.__dict__['raw'] = self.e164() #.lstrip('+')
        return rv

    @raw.setter
    def raw(self, value):
        self.__dict__['raw'] = value

    @classmethod
    def from_e164(cls, value):
        return cls.from_raw(value.lstrip('+'))

    @classmethod
    def from_raw(cls, value):
        return cls(
            country_code=value[:3],
            national_number=value[3:]
        )

    @classmethod
    def parse(cls, number, region=None, keep_raw_input=False, numobj=None, _check_region=True):
        return phonenumbers.parse(
                number,
                region=region,
                keep_raw_input=keep_raw_input,
                numobj=cls() if numobj is None else numobj,
                _check_region=_check_region
            )

    def national(self):
        return self.format(PhoneNumberFormat.NATIONAL)

    def international(self):
        return self.format(PhoneNumberFormat.INTERNATIONAL)

    def e164(self):
        return self.format(PhoneNumberFormat.E164)
    
    def carrier(self, lang='en'):
        return carrier.name_for_number(self, lang)

    def region(self, lang='en'):
        return carrier.region_code_for_number(self)

    def format(self, fmt):
        return format_number(self, fmt)

    def endswith(self, suffix, start=0, end = -1):
        return self.raw.endswith(suffix, start, end)

    def startswith(self, prefix, start=0, end = -1):
        return self.raw.startswith(prefix, start, end)

    def __contains__(self, other):
        return self.raw.__contains__(other)

    def __eq__(self, other):
        if isinstance(other, (PhoneNumber, str)):
            return self.raw == str(other)
        elif isinstance(other, BasePhoneNumber):
            return super().__eq__(other)
        else:
            return False

    def __len__(self):
        return len(self.raw)

    def __unicode__(self):
        return self.raw

    def __getitem__(self, key):
        return self.raw.__getitem__(key)

    def __iter__(self):
        return iter(self.raw)

    def __str__(self):
        return self.raw

    def __json__(self):
        return self.raw

    def clear(self):
        self.raw = None
        return super().clear()

    def merge_from(self, other):
        self.raw = None
        return super().merge_from(other)

    @classmethod
    def __get_validators__(cls):
        def validate(v):
            try:
                rv = v if isinstance(v, cls) else cls.parse(str(v))
            except NumberParseException as e:
                raise ValueError(f'must be a valid phone number.')
                # raise ValueError(e._msg)
            else:
                if not is_possible_number(rv):
                    raise ValueError(f'must be a valid phone number.')
                return rv

        yield validate

    @classmethod
    def __modify_schema__(cls, field_schema: dict[str, t.Any]) -> None:
        field_schema.update(type='string', format=f'phone-number', example='+XXX XXXXXXXXX')






parse = PhoneNumber.parse

