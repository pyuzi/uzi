import logging
import typing as t

from functools import cache

from djx.common.proxy import unproxy
from djx.common.utils import export
from djx.common.typing import get_all_type_hints, get_origin


from .common import Injectable, T_Injected, T_Default


from .exc import InjectorKeyError




logger = logging.getLogger(__name__)


