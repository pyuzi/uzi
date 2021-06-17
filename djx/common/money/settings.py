from django.conf import settings

from djx.common.utils import setdefault

from moneyed import DEFAULT_CURRENCY_CODE



DEFAULT_CURRENCY = setdefault(settings, "DEFAULT_CURRENCY", DEFAULT_CURRENCY_CODE)

ALLOWED_CURRENCIES = setdefault(settings, "CURRENCIES", [DEFAULT_CURRENCY,])

