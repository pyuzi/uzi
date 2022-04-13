from copy import copy, deepcopy
from inspect import isawaitable
from time import sleep
from types import GenericAlias, new_class
import typing as t
import attr
import pytest


from xdi.providers import Provider
from xdi._dependency import Dependency


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_notset = object()

_T = t.TypeVar("_T")
_T_Pro = t.TypeVar("_T_Pro", bound=Provider, covariant=True)


class ProviderTestCase(t.Generic[_T_Pro]):

    type_: t.ClassVar[type[_T_Pro]] = Provider

    value = _notset

    _provider: _T_Pro

    def __class_getitem__(cls, params: t.Union[type[_T_Pro], tuple[type[_T_Pro]]]):
        if isinstance(params, tuple):
            param = params[0]
        else:
            param = params

        if isinstance(param, (type, GenericAlias)):
            tp = new_class(
                f"{cls.__name__}", (cls,), None, lambda ns: ns.update(type_=param)
            )
            params = (_T_Pro,)
        else:
            tp = cls
        return GenericAlias(tp, params)

    @pytest.fixture
    def cls(self):
        return self.type_

    @pytest.fixture
    def new_kwargs(self):
        return {}

    @pytest.fixture
    def new(self, cls, concrete, new_kwargs):
        return lambda c=concrete, **kw: cls(c, **{**new_kwargs, **kw})

    @pytest.fixture(autouse=True)
    def _setup_provider(self, subject, cls):
        assert subject.__class__ is cls
        self._provider = subject

    @pytest.fixture
    def subject(self, new):
        return new()

    @pytest.fixture
    def value_factory(self):
        return lambda: object()

    @pytest.fixture
    def value_setter(self, value_factory):
        def fn(*a, **kw):
            self.value = val = value_factory(*a, **kw)
            return val

        return fn

    def test_basic(self, subject: _T_Pro, cls: type[_T_Pro]):
        assert isinstance(subject, Provider)
        assert subject.__class__ is cls
        assert cls.__slots__ is cls.__dict__["__slots__"]

    def test_copy(self, subject: _T_Pro):
        cp = copy(subject)
        assert cp.__class__ is subject.__class__
        assert cp.concrete == subject.concrete
        assert cp != subject

    def test_deepcopy(self, subject: _T_Pro):
        cp = deepcopy(subject)
        assert cp.__class__ is subject.__class__
        assert cp != subject

    def test_not_mutable(self, subject: _T_Pro):
        for atr in attr.fields(subject.__class__):
            try:
                subject.__setattr__(atr.name, getattr(subject, atr.name, None))
            except AttributeError:
                continue
            else:
                raise AssertionError(f"mutable: {atr.name!r} -> {subject}")

    def test_set_container(self, subject: _T_Pro, container):
        assert subject.container is None
        subject.set_container(container).set_container(container)
        assert subject.container is container

    @xfail(raises=AttributeError, strict=True)
    def test_xfail_multiple_set_container(self, subject: _T_Pro, Container):
        assert subject.container is None
        subject.set_container(Container()).set_container(Container())

    def test_is_default(self, subject: _T_Pro):
        subject.default()
        assert subject.is_default is True
        subject.default(False)
        assert subject.is_default is False

    def test_is_final(self, subject: _T_Pro):
        subject.final()
        assert subject.is_final is True
        subject.final(False)
        assert subject.is_final is False

    @xfail(raises=AttributeError, strict=True)
    @parametrize(
        ["op", "args"],
        [
            ("default", ()),
            ("final", ()),
            ("set_container", (None,)),
        ],
    )
    def test_xfail_frozen(self, subject: _T_Pro, op, args):
        subject._freeze()
        fn = getattr(subject, op, None)
        assert fn
        fn(*args)

    @xfail(raises=NotImplementedError, strict=False)
    def test_make_dependency(self, subject: _T_Pro, scope):
        dep = subject._make_dependency(_T, scope)
        assert isinstance(dep, subject._dependency_class or Dependency)




class AsyncProviderTestCase(ProviderTestCase):

    @pytest.fixture
    def value_factory(self):
        async def fn():
            return object()

        return fn

    @pytest.fixture
    def value_setter(self, value_factory):
        async def sfn(*a, **kw):
            self.value = val = await value_factory(*a, **kw)
            return val

        return sfn

