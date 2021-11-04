import typing as t 

from djx.common.utils import export

from djx.common.enum import IntEnum, auto


if t.TYPE_CHECKING:
    from . import Provider
    ProviderType = type[Provider]



@export()
class KindOfProvider(IntEnum, fields='default_impl', frozen=False):
    value: 'KindOfProvider'       = auto()
    alias: 'KindOfProvider'       = auto()
    
    func: 'KindOfProvider'        = auto()
    type: 'KindOfProvider'        = auto()
    meta: 'KindOfProvider'        = auto()
    
    factory: 'KindOfProvider'     = auto()
    resolver: 'KindOfProvider'    = auto()

    if t.TYPE_CHECKING:
        default_impl: 'ProviderType'

    def _set_default_impl(self, cls: 'ProviderType'):
        if self.default_impl is not None:
            raise ValueError(f'{cls}. {self}.impl already set to {self.default_impl}')
        self.__member_data__[self.name].default_impl = cls
        cls.kind = self
        return cls

    @classmethod
    def _missing_(cls, val):
        if val is None:
            return cls.factory
    
