import typing as t

from collections.abc import Hashable

import portion as base


Bound = base.Bound
inf = base.inf


_T = t.TypeVar('_T',  bound=Hashable, covariant=True)


class Atomic(t.NamedTuple):
    left: Bound
    lower: _T
    upper: _T
    right: Bound

    


base.interval.Atomic = Atomic


Atomic = base.interval.Atomic



def from_atomic(left, lower, upper, right):
    """
    Create an Interval instance containing a single atomic interval.

    :param left: either CLOSED or OPEN.
    :param lower: value of the lower bound.
    :param upper: value of the upper bound.
    :param right: either CLOSED or OPEN.
    """
    return Interval.from_atomic(left, lower, upper, right)

base.Interval.from_atomic = from_atomic




def open(lower, upper):
    """
    Create an open interval with given bounds.

    :param lower: value of the lower bound.
    :param upper: value of the upper bound.
    :return: an interval.
    """
    return Interval.from_atomic(Bound.OPEN, lower, upper, Bound.OPEN)


def closed(lower, upper):
    """
    Create a closed interval with given bounds.

    :param lower: value of the lower bound.
    :param upper: value of the upper bound.
    :return: an interval.
    """
    return Interval.from_atomic(Bound.CLOSED, lower, upper, Bound.CLOSED)


def openclosed(lower, upper):
    """
    Create a left-open interval with given bounds.

    :param lower: value of the lower bound.
    :param upper: value of the upper bound.
    :return: an interval.
    """
    return Interval.from_atomic(Bound.OPEN, lower, upper, Bound.CLOSED)


def closedopen(lower, upper):
    """
    Create a right-open interval with given bounds.

    :param lower: value of the lower bound.
    :param upper: value of the upper bound.
    :return: an interval.
    """
    return Interval.from_atomic(Bound.CLOSED, lower, upper, Bound.OPEN)


def singleton(value):
    """
    Create a singleton interval.

    :param value: value of the lower and upper bounds.
    :return: an interval.
    """
    return Interval.from_atomic(Bound.CLOSED, value, value, Bound.CLOSED)


def empty():
    """
    Create an empty interval.

    :return: an interval.
    """
    return Interval.from_atomic(Bound.OPEN, inf, -inf, Bound.OPEN)




class Interval(base.Interval, t.Generic[_T]):
    """
    This class represents an interval.

    An interval is an (automatically simplified) union of atomic intervals.
    It can be created with Interval.from_atomic(), by passing intervals to
    __init__, or by using one of the helpers provided in this module (open,
    closed, openclosed, etc.)
    """

    __slots__ = ("__weakref__",)

    lower: _T
    upper: _T

    # @property
    # def start(self):
    #     if self.atomic:
    #         return self.
    #     return self.star
        
    # @classmethod
    # def __modify_schema__(cls, field_schema: dict[str, t.Any]) -> None:
    #     field_schema.update(type='string', format='date-time', example=str(cls.now()))

    # @classmethod
    # def __get_validators__(cls):
    #     yield cls._validate

    # @classmethod
    # def _validate(cls, v, **kwargs):
    #     if isinstance(v, )
    
    # @property
    # def includes_lower(self):
    #     return self.left is Bound.CLOSED

    # @property
    # def includes_upper(self):
    #     return self.right is Bound.CLOSED

    @classmethod
    def from_atomic(cls, left, lower, upper, right) -> 'Interval[_T]':
        """
        Create an Interval instance containing a single atomic interval.

        :param left: either CLOSED or OPEN.
        :param lower: value of the lower bound.
        :param upper: value of the upper bound.
        :param right: either CLOSED or OPEN.
        """
        rv = cls()
        left = left if lower not in [inf, -inf] else Bound.OPEN
        right = right if upper not in [inf, -inf] else Bound.OPEN

        rv._intervals = [Atomic(left, lower, upper, right)]
        
        return cls() if rv.empty else rv

    @classmethod
    def from_str(cls, val: str) -> 'Interval[_T]':
        """
        Create an Interval instance containing a single atomic interval.

        :param left: either CLOSED or OPEN.
        :param lower: value of the lower bound.
        :param upper: value of the upper bound.
        :param right: either CLOSED or OPEN.
        """
        pass

    def as_str(self) -> str:
        if self.empty:
            return "()"

        string = []
        for interval in self._intervals:
            if interval.lower == interval.upper:
                string.append("[{}]".format(repr(interval.lower)))
            else:
                string.append(
                    "{}{},{}{}".format(
                        "[" if interval.left == Bound.CLOSED else "(",
                        repr(interval.lower),
                        repr(interval.upper),
                        "]" if interval.right == Bound.CLOSED else ")",
                    )
                )
        return " | ".join(string)

    # def __json__(self):
    #     return self.as_str()

    def __str__(self):
        return self.as_str()

    def __repr__(self):
        return f'{self.__class__.__name__}({self})'












# from .exc import IntervalException

strip = lambda a: a.strip()


class IntervalStringParser(object):
    def parse_string(self, value):
        if ',' not in value:
            return self.parse_hyphen_range(value)
        else:
            return self.parse_bounded_range(value)

    def parse_bounded_range(self, value):
        values = value.strip()[1:-1].split(',')
        lower, upper = map(strip, values)
        return (
            [lower, upper],
            value[0] == '[',
            value[-1] == ']'
        )

    def parse_hyphen_range(self, value):
        """
        Parse hyphen ranges such as: 2 - 5, -2 - -1, -3 - 5
        """
        values = value.strip().split('-')
        values = list(map(strip, values))
        if len(values) == 1:
            lower = upper = value.strip()
        elif len(values) == 2:
            lower, upper = values
            if lower == '':
                # Parse range such as '-3'
                upper = '-' + upper
                lower = upper
        else:
            if len(values) > 4:
                raise IntervalException(
                    'Unknown interval format given.'
                )
            values_copy = []
            for key, value in enumerate(values):
                if value != '':
                    try:
                        if values[key - 1] == '':
                            value = '-' + value
                    except IndexError:
                        pass
                    values_copy.append(value)
            lower, upper = values_copy

        return [lower, upper], True, True


class IntervalParser(t.Generic[_T]):

    def parse_object(self, obj) -> Atomic[_T]:
        return obj.lower, obj.upper, obj.lower_inc, obj.upper_inc

    def parse_sequence(self, seq) -> Atomic[_T]:
        lower, upper = seq
        if isinstance(seq, tuple):
            return Bound.OPEN, lower, upper, Bound.OPEN
        else:
            return Bound.CLOSED, lower, upper, Bound.CLOSED

    def parse_single_value(self, value) -> Atomic[_T]:
        return Bound.CLOSED, value, value, Bound.CLOSED

    def __call__(self, bounds, left=None, right=None):
        if isinstance(bounds, (list, tuple)):
            values = self.parse_sequence(bounds)
        elif hasattr(bounds, 'lower') and hasattr(bounds, 'upper'):
            values = self.parse_object(bounds)
        else:
            values = self.parse_single_value(bounds)
        values = list(values)
        if left is not None:
            values[2] = left
        if right is not None:
            values[3] = right
        return values