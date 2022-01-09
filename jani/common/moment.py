from functools import cache
import pytz
import arrow as base
import typing as t

from arrow import parser
from datetime import datetime, tzinfo, date
from dateutil import tz


from jani.core import settings
from jani.di import ioc
from jani.common.utils import getitem
from jani.common.locale import Locale


from arrow.arrow import DEFAULT_LOCALE as _DEFAULT_LOCALE

Type = type

T_Moment = t.TypeVar('T_Moment', bound='Moment', covariant=True)
T_Tzinfo = t.TypeVar('T_Tzinfo', bound=tzinfo, covariant=True)


_T_FRAMES = t.Literal[
    "year",
    "years",
    "month",
    "months",
    "day",
    "days",
    "hour",
    "hours",
    "minute",
    "minutes",
    "second",
    "seconds",
    "microsecond",
    "microseconds",
    "week",
    "weeks",
    "quarter",
    "quarters",
]


ioc.alias(tzinfo, T_Tzinfo, at='main')

ParserError = parser.ParserError



if t.TYPE_CHECKING:
    get = base.get
    now = base.now
    utcnow = base.utcnow
else:
    def get(*args, **kwargs) -> T_Moment:
        return moment.get(*args, **kwargs)

    def now(tz: t.Union[T_Tzinfo, str] = None) -> T_Moment:
        return moment.now(tz)

    def utcnow() -> T_Moment:
        return moment.utcnow()



# In order to avoid accessing settings at compile time,
# wrap the logic in a function and cache the result.
@ioc.injectable(at='main', abstract=T_Tzinfo, cache=True)
def _default_timezone():
    """
    Return the default time zone as a tzinfo instance.

    This is the time zone defined by settings.TIME_ZONE.
    """
    if _tz := getitem(settings, 'TIME_ZONE', None):
        return pytz.timezone(_tz)
    
    return tz.tzlocal()




def get_current_timezone():
    return ioc.make(tzinfo)


def get_default_timezone():
    return ioc.make(T_Tzinfo)




class Moment(base.Arrow):

    min: t.ClassVar["Moment"]
    max: t.ClassVar["Moment"]

    FORMAT: t.ClassVar[str] = None
    
    @classmethod
    def fromdatetime(cls, dt: datetime, tzinfo = None) -> "Moment":
        """Constructs an :class:`Moment <moment.moment.Moment>` object from a ``datetime`` and
        optional replacement timezone.

        :param dt: the ``datetime``
        :param tzinfo: (optional) A :ref:`timezone expression <tz-expr>`.  Defaults to ``dt``'s
            timezone, or UTC if naive.

        Usage::

            >>> dt
            datetime.datetime(2021, 4, 7, 13, 48, tzinfo=tzfile('/usr/share/zoneinfo/US/Pacific'))
            >>> moment.Moment.fromdatetime(dt)
            <Moment [2021-04-07T13:48:00-07:00]>

        """

        if tzinfo is None:
            if dt.tzinfo is None:
                tzinfo = get_default_timezone()
            else:
                tzinfo = dt.tzinfo
        elif tzinfo == 'local':
                tzinfo = get_current_timezone()

        return cls(
            dt.year,
            dt.month,
            dt.day,
            dt.hour,
            dt.minute,
            dt.second,
            dt.microsecond,
            tzinfo,
            fold=getattr(dt, "fold", 0),
        )

    @classmethod
    def fromdate(cls, date: date, tzinfo = None) -> "Moment":
        """Constructs an :class:`Moment <moment.moment.Moment>` object from a ``date`` and optional
        replacement timezone.  All time values are set to 0.

        :param date: the ``date``
        :param tzinfo: (optional) A :ref:`timezone expression <tz-expr>`.  Defaults to UTC.

        """

        if tzinfo is None:
            tzinfo = get_default_timezone()
        elif tzinfo == 'local':
            tzinfo = get_current_timezone()

        return cls(date.year, date.month, date.day, tzinfo=tzinfo)

    @classmethod
    def fromtimestamp(
        cls,
        timestamp: t.Union[int, float, str],
        tzinfo = None,
    ) -> "Moment":
        """Constructs an :class:`Moment <moment.moment.Moment>` object from a timestamp, converted to
        the given timezone.

        :param timestamp: an ``int`` or ``float`` timestamp, or a ``str`` that converts to either.
        :param tzinfo: (optional) a ``tzinfo`` object.  Defaults to local time.

        """

        if tzinfo is None or tzinfo == 'local':
            tzinfo = get_current_timezone()
        elif isinstance(tzinfo, str):
            tzinfo = parser.TzinfoParser.parse(tzinfo)
        
        return super().fromtimestamp(timestamp, tzinfo)

    def to(self, tz) -> "Moment":
        """Returns a new :class:`Moment <moment.moment.Moment>` object, converted
        to the target timezone.

        :param tz: A :ref:`timezone expression <tz-expr>`.

        Usage::

            >>> utc = moment.utcnow()
            >>> utc
            <Moment [2013-05-09T03:49:12.311072+00:00]>

            >>> utc.to('US/Pacific')
            <Moment [2013-05-08T20:49:12.311072-07:00]>

            >>> utc.to(tz.tzlocal())
            <Moment [2013-05-08T20:49:12.311072-07:00]>

            >>> utc.to('-07:00')
            <Moment [2013-05-08T20:49:12.311072-07:00]>

            >>> utc.to('local')
            <Moment [2013-05-08T20:49:12.311072-07:00]>

            >>> utc.to('local').to('utc')
            <Moment [2013-05-09T03:49:12.311072+00:00]>

        """
        if tz == 'local':
            tz = get_current_timezone()
        
        return super().to(tz)

    def format(self, fmt: str = None, locale: str = _DEFAULT_LOCALE) -> str:
        """Returns a string representation of the :class:`Moment <moment.moment.Moment>` object,
        formatted according to the provided format string.

        :param fmt: the format string.
        :param locale: the locale to format.

        Usage::

            >>> moment.utcnow().format('YYYY-MM-DD HH:mm:ss ZZ')
            '2013-05-09 03:56:47 -00:00'

            >>> moment.utcnow().format('X')
            '1368071882'

            >>> moment.utcnow().format('MMMM DD, YYYY')
            'May 09, 2013'

            >>> moment.utcnow().format()
            '2013-05-09 03:56:47 -00:00'

        """
        return super().format(fmt or self.FORMAT or "YYYY-MM-DD HH:mm:ssZZ", locale)

    def __str__(self) -> str:
        if self.FORMAT is None:
            return super().__str__()
        else:
            return self.format()

    @classmethod
    def __modify_schema__(cls, field_schema: dict[str, t.Any]) -> None:
        field_schema.update(type='string', format='date-time', example=str(cls.now()))

    @classmethod
    def __get_validators__(cls):
        yield cls._validate

    @classmethod
    def _validate(cls, v, **kwargs):
        field = kwargs.get('field')
        tz = getitem(field, 'tzinfo', None)
        if not isinstance(v, cls):
            
            if isinstance(v, str):
                if fmts := getitem(field, 'allowed_format', None):
                    fmt = list(fmts) if isinstance(fmts, tuple) else fmts
                    v = get(v, fmt)
                else:
                    v = get(v)
            else:
                v = get(v)
        
        if tz:
            v = v.to(tz)
        return v 

    def __json__(self):
        return str(self)
    



@cache
def FormatedMoment(fmt):
    class _FormatedMoment(Moment):

        FORMAT: t.Final[str] = fmt

    return _FormatedMoment



@ioc.injectable(at='any', cache=True)
class MomentFactory(base.ArrowFactory, t.Generic[T_Moment]):

    type: Type[T_Moment] = Moment

    def __init__(self, locale: Locale = None, type: Type[Moment]=None) -> None:
        self.locale_id = locale and f'{locale.language}-{locale.territory}'.lower()
        if type is not None:
            self.type = type

    @property
    def max(self):
        return self.type.max
        
    @property
    def min(self):
        return self.type.min
    
    @property
    def range(self):
        return self.type.range
    
    @property
    def span_range(self):
        return self.type.span_range

    def cast(self, val: t.Any) -> T_Moment:
        if type(val) is self.type:
            return val
        else:
            return self.get(val)

    def get(self, *args: t.Any, **kwargs: t.Any) -> T_Moment:
        # if kwargs.get('locale') is None:
        #     if locale_id := self.locale_id:
        #         kwargs['locale'] = locale_id

        if not args or args[0] is None:
            args = args[1:]
            kwargs.setdefault('tzinfo', get_default_timezone())

        return super().get(*args, **kwargs)

    def now(self, tz: t.Union[tzinfo, str] = None) -> T_Moment:
        if tz is None:
            tz = get_current_timezone()
        elif not isinstance(tz, tzinfo):
            tz = parser.TzinfoParser.parse(tz)

        return self.type.now(tz)

    def utcnow(self) -> T_Moment:
        self.type.utcnow()

    def range(self, start) -> T_Moment:
        self.type.range()

    def __call__(self, *args: t.Any, **kwargs: t.Any) -> T_Moment:
        return self.get(*args, **kwargs)


ioc.alias(MomentFactory[Moment], MomentFactory)

moment: MomentFactory[Moment] = ioc.proxy(MomentFactory)

