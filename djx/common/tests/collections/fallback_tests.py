from typing_extensions import Literal
import typing as t
import inspect as ins
import pytest
from typing import Optional, Union

from ..collections import fa

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



class FallbackDictTests:

    def test_basic(self):
        

        assert 1, '\n'
 

