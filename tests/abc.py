from inspect import isfunction, ismethod
from types import GenericAlias, new_class
import typing as t
import pytest


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T_Sub = t.TypeVar("_T_Sub")


class BaseTestCase(t.Generic[_T_Sub]):

    type_: t.ClassVar[type[_T_Sub]] = None

    def __class_getitem__(cls, params: t.Union[type[_T_Sub], tuple[type[_T_Sub]]]):
        if isinstance(params, tuple):
            param = params[0]
        else:
            param = params

        if isinstance(param, (type, GenericAlias)):
            tp = new_class(
                f"{cls.__name__}", (cls,), None, lambda ns: ns.update(type_=param)
            )
            params = (_T_Sub,)
        else:
            tp = cls
        return GenericAlias(tp, params)

    @pytest.fixture
    def cls(self):
        return self.type_

    @pytest.fixture
    def value_setter(self, value_factory):
        def fn(*a, **kw):
            self.value = val = value_factory(*a, **kw)
            return val

        return fn

    @pytest.fixture
    def immutable_attrs(self, cls):
        return [
            a
            for a in dir(cls)
            if not (a[:2] == "__" == a[-2:] or isfunction(getattr(cls, a)))
        ]

    def assert_immutable(self, sub: _T_Sub, immutable_attrs):
        it = iter(immutable_attrs)
        for atr in it:
            try:
                setattr(sub, atr, getattr(sub, atr, None))
            except AttributeError:
                continue
            else:
                raise AssertionError(
                    f"attribute `{sub.__class__.__qualname__}.{atr}` is mutable"
                )
        return sub
