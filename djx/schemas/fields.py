# from pydantic.fields import 

from typing import Any
from flex.phonenumber import PhoneNumber


class PhoneNumber(PhoneNumber):

    @classmethod
    def __modify_schema__(cls, field_schema: dict[str, Any]) -> None:
        field_schema.update(type='string', format=f'phone-number')
