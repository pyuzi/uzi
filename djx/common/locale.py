from functools import cache
import typing as t
from babel import Locale as Babel, default_locale as env_locale
from babel import numbers
from babel.core import LOCALE_ALIASES, get_locale_identifier
import babel

from djx.di import di
from djx.common.utils import cached_property, export
from djx.common.collections import fallbackdict


if not t.TYPE_CHECKING:
    __all__ = [
        'locale',
    ]
    

if not t.TYPE_CHECKING:
    parse_locale = cache(babel.parse_locale)
else:
    def parse_locale(val: str, sep:str='_') -> tuple[str, 'OptStr', 'OptStr', 'OptStr']:
        ...        




_val_settings = None
def _get_settings():
    global _val_settings
    if _val_settings is None:
        try:
            from django.conf import settings
            bool(settings)
        except Exception:
            return None
        else:
            _val_settings = settings
    return _val_settings






OptStr = t.Optional[str]


LOCALE = t.TypeVar('LOCALE', bound=str)
LOCALE_ID = t.TypeVar('LOCALE_ID', bound=tuple[str, OptStr, OptStr, OptStr])
LangCategory = t.Union[t.Literal['LOCALE', 'LANGUAGE', 'LC_ALL', 'LC_CTYPE', 'LANG'], str]










def _cat_fallback(k):
    if isinstance(k, str) and k.startswith('LC_'):
        _cat_settings_keys[k] = k,
    else:
        _cat_settings_keys[k] = ()
    return _cat_settings_keys[k]


_cat_settings_keys =fallbackdict[str, list[str]](
    _cat_fallback,
    LOCALE=['LOCALE', 'LANGUAGE_CODE'],
    LANGUAGE=['LANGUAGE_CODE',],
    LANG=['LANGUAGE_CODE'],
    LC_ALL=['LANGUAGE_CODE'],

)

_locale_sep = fallbackdict[str, str]('_', LANGUAGE_CODE='-')


@di.injectable('main', abstract=LOCALE, cache=True)
def default_locale(category: LangCategory=None, 
                    aliases=LOCALE_ALIASES):
    category = category or 'LOCALE'
    rv = None
    if (settings := _get_settings()):
        for k in _cat_settings_keys[category]:
            rv = getattr(settings, k, None)
            rv = rv and get_locale_identifier(parse_locale(rv, _locale_sep[k]))
            if rv: 
                break

    return rv or env_locale(category, aliases)
    




@di.injectable(abstract=LOCALE_ID)
def _parse_locale_id(id: LOCALE):
    return parse_locale(id)


@export()
@di.injectable('main', cache=True)
@di.injectable('local', cache=True)
class Locale(Babel):

    t.overload
    def __init__(self, language: str, territory: str=None, script=None, variant=None):
        ...
    t.overload
    def __init__(self, *identifier: LOCALE_ID, **kwds):
        ...
    def __init__(self, *identifier: LOCALE_ID, **kwds):
        super().__init__(*identifier, **kwds)

    @property
    def local_currency(self):
        return self.local_currencies[0]

    @cached_property
    def local_currencies(self):
        return numbers.get_territory_currencies(self.territory)

    if t.TYPE_CHECKING:
        def __call__(self):
            return self




locale: Locale = di.proxy(Locale, callable=True)

