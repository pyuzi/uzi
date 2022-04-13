from types import GenericAlias, new_class
import typing as t
import pytest





xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T_Sub = t.TypeVar('_T_Sub')



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

