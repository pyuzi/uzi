

from contextlib import AbstractAsyncContextManager
from typing import TypeVar


T_HttpClient = TypeVar('T_HttpClient', bound=AbstractAsyncContextManager['ClientSession'], covariant=True)
T_HttpSession = TypeVar('T_HttpSession', bound='ClientSession', covariant=True)