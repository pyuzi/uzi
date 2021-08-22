import copy
import typing as t

from decimal import Decimal


from djx.common.locale import get_locale_currency



from .money import Money, MoneyAbc





import babel.numbers


class Monies:
    """This class represents a set of multi-currency Money objects and provides 
    math functionality. Monies can be added, subtracted, multiplied,
    divided, absolute'ed, and have their sign changed.

    Examples:

        Example use::

            Monies([Money(100, 'USD'), Money(200, 'EUR')])

            # Or in short form
            Monies(100, 'USD', 200, 'EUR')

    .. important::

        Monies can also be compared, but note that this requires a currency conversion step.
        Therefore it is possible that monies will compare differently as exchange rates
        change over time.

    """

    __slots__ = ('_money_obs', '_by_currency')

    def __init__(self, _money_obs=None, *args):
        all_args = [_money_obs] + list(args)
        if len(all_args) % 2 == 0:
            _money_obs = []
            for i in range(0, len(all_args) - 1, 2):
                _money_obs.append(Money(all_args[i], all_args[i + 1]))

        self._money_obs = tuple(_money_obs or [])
        self._by_currency = {m.currency.code: m for m in self._money_obs}
        if len(self._by_currency) != len(self._money_obs):
            raise ValueError(
                "Duplicate currency provided. All Money instances must have a unique currency."
            )

    def __str__(self):
        def fmt(money):
            return babel.numbers.format_currency(money.amount, currency=money.currency.code)

        return ", ".join(map(fmt, self._money_obs)) or "No values"

    def __json__(self):
        return self._money_obs

    def __repr__(self):
        return "Monies: {}".format(self.__str__())

    def __getitem__(self, currency):
        if hasattr(currency, "code"):
            currency = currency.code
        elif not isinstance(currency, str) or len(currency) != 3:
            raise ValueError("Currencies must be a string of length three, not {}".format(currency))

        try:
            return self._by_currency[currency]
        except KeyError:
            return Money(0, currency)

    def __add__(self, other):
        if isinstance(other, Monies):
            others = other._by_currency.items()
        elif isinstance(other, Money):
            others = [(other.currency.code, other.amount)]
        else:
            return NotImplemented
            # raise TypeError(
            #     "Can only add/subtract Monies instances, not Monies and {}.".format(type(other))
            # )

        by_currency = copy.deepcopy(self._by_currency)
        for other_currency, other_money in others:
            by_currency[other_currency] = other_money + self[other_currency]
        return self.__class__(by_currency.values())

    def __sub__(self, other):
        return self.__add__(-other)

    def __neg__(self):
        return self.__class__([-m for m in self._money_obs])

    def __pos__(self):
        return self.__class__([+m for m in self._money_obs])

    def __mul__(self, other):
        if isinstance(other, Monies):
            raise TypeError("Cannot multiply two Monies instances.")
        elif isinstance(other, float):
            raise LossyCalculationError(
                "Cannot multiply a Monies by a float. Use a Decimal or an int."
            )
        return self.__class__([m * other for m in self._money_obs])

    def __truediv__(self, other):
        if isinstance(other, Monies):
            raise TypeError("Cannot divide two Monies instances.")
        elif isinstance(other, float):
            raise LossyCalculationError(
                "Cannot divide a Monies by a float. Use a Decimal or an int."
            )
        return self.__class__([m / other for m in self._money_obs])

    def __abs__(self):
        return self.__class__([abs(m) for m in self._money_obs])

    def __bool__(self):
        return any(bool(m) for m in self._money_obs)

    def __iter__(self):
        return iter(self._money_obs)

    def __len__(self):
        return len(self._money_obs)

    def __eq__(self, other):
        if other == 0:
            # Support comparing to integer/Decimal zero as it is useful
            return not self.__bool__()
        # elif not isinstance(other, (Monies, )):

        #     return NotImplemented
        #     # raise TypeError(
        #     #     "Can only compare Monies objects to other "
            #     "Monies objects, not to type {}".format(type(other))
            # )
        return not self - other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if isinstance(other, MoneyAbc):
            other = self.__class__([other])
        # We can compare against non-monies 0-values, but otherwise we have to
        # compare against a Monies (otherwise we won't know what currency we are
        # dealing with)
        if isinstance(other, (float, int, Decimal)) and other == 0:
            other = self.__class__()
        if not isinstance(other, Monies):
            return NotImplemented

        # If we can confidently simplify the values to
        # -1, 0, and 1, and the values are different, then
        # just compare those.
        try:
            self_simplified = self._simplify()
            other_simplified = other._simplify()
            if self_simplified != other_simplified:
                return self_simplified < other_simplified
        except CannotSimplifyError:
            pass

        if len(self._money_obs) == 1 and self.currencies() == other.currencies():
            # Shortcut if we have a single value with the same currency
            return self._money_obs[0] < other._money_obs[0]
        else:
            cur = get_locale_currency()
            money = self.normalise(cur)._money_obs[0]
            other_money = other.normalise(cur)._money_obs[0]
            return money < other_money

    def __gt__(self, other):
        return not self < other and not self == other

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return self > other or self == other

    def money(self, currency=None):
        """Normalise this monies into a single currency

        Args:
            currency (str): Destination currency

        Returns:
            (Money): A Money value in the specified currency
        """
        if not self._money_obs:
            return Money(0, currency)
        elif len(self._money_obs) == 1:
            rv = self._money_obs[0]
            if currency is None or str(currency).upper() == rv.currency.code:
                return copy.copy(rv) 
        
        raise TypeError(f'cannot converter currencies at the moment.')
        
        # out: Money = Money(currency=currency)
        # for money in self._money_obs:
        #     out += converter.convert(money, currency)
        # return out
    
    def monies(self):
        """Get a list of the underlying ``Money`` instances

        Returns:
            ([Money]): A list of zero or money money instances. Currencies will be unique.
        """
        return [copy.copy(m) for m in self._money_obs]

    def currencies(self):
        """Get all currencies with non-zero values"""
        return list(self._by_currency)
        # return [m.currency.code for m in self.monies() if m.amount]

    def normalise(self, currency=None):
        """Normalise this monies into a single currency

        Args:
            currency (str): Destination currency

        Returns:
            (Monies): A new monies object containing a single Money value in the specified currency
        """
        return self.__class__([self.money(currency)])

    def _is_positive(self):
        return all([m.amount > 0 for m in self.monies()]) and self.monies()

    def _is_negative(self):
        return all([m.amount < 0 for m in self.monies()]) and self.monies()

    def _is_zero(self):
        return not self.monies() or all([m.amount == 0 for m in self.monies()])

    def _simplify(self):
        if self._is_positive():
            return 1
        elif self._is_negative():
            return -1
        elif self._is_zero():
            return 0
        else:
            raise CannotSimplifyError()

    @classmethod
    def __get_validators__(cls):
        pass




class MoenyError(Exception):
    pass



class CannotSimplifyError(MoenyError):
    """Used internally by Currency class"""
    ...


class LossyCalculationError(MoenyError, TypeError):
    """Raised to prevent a lossy or imprecise calculation from occurring.

    Typically this may happen when trying to multiply/divide a monetary value
    by a float.
    """
    ...

