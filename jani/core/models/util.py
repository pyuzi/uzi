import typing as t 
import re

from jani.common.functools import export
from jani.common.data import DataPath




@export()
class LookupDataPath(DataPath):

    __slots__ = ()

    _re_look = re.compile(r'(?<!^)__(?!$)')

    @classmethod
    def _iter_path(cls, path) -> None:
        if isinstance(path, str):
            path = cls._re_look.sub('.', path)
        return super()._iter_path(path)
    
    @property
    def lookup(self):
        return self.value.replace('.', '__')