import typing as t
from abc import abstractmethod
from collections.abc import Callable, Hashable

from . import FrozenDict, private_setattr


_T_Obj = t.TypeVar("_T_Obj")
_T_Expr = t.TypeVar("_T_Expr")
_T_Default = t.TypeVar("_T_Default")
_T_Args = t.TypeVar("_T_Args")
_T_Kwargs = t.TypeVar("_T_Kwargs")
_T_Item = t.TypeVar("_T_Item", int, str, Hashable)

_object_new = object.__new__


class ExpressionError(Exception):
    ...  # pragma: no cover


class EvaluationError(ExpressionError):
    @classmethod
    def wrap(cls, exc: Exception):
        if _cls := _eval_exc_types.get(exc.__class__):
            return exc if _cls is exc.__class__ else _cls(exc)
        elif cls is EvaluationError:
            for e in _eval_exc_types:
                if isinstance(exc, e):
                    return _eval_exc_types[e](exc)
                    break
            return exc  # (_cls or cls)(exc)
        else:
            return cls(exc)


class AttributeEvaluationError(EvaluationError, AttributeError):
    ...  # pragma: no cover


class KeyEvaluationError(EvaluationError, KeyError):
    ...  # pragma: no cover


class IndexEvaluationError(EvaluationError, IndexError):
    ...  # pragma: no cover


class CallEvaluationError(EvaluationError, TypeError):
    ...  # pragma: no cover


_eval_exc_types = {
    AttributeError: AttributeEvaluationError,
    KeyError: KeyEvaluationError,
    IndexError: IndexEvaluationError,
    LookupError: EvaluationError,
    CallEvaluationError: CallEvaluationError,
}


@private_setattr
class Expression(t.Generic[_T_Expr, _T_Obj]):
    __slots__ = ("__expr__",)

    __expr__: _T_Expr

    __evaluation_errors__ = (EvaluationError,)

    def __new__(cls, expr: _T_Expr):
        self = _object_new(cls)
        self.__setattr(__expr__=expr)
        return self

    def __eq__(self, x):
        if isinstance(x, self.__class__):
            return x.__expr__ == self.__expr__
        # elif isinstance(x, self.__expr__.__class__):
        #     return x == self.__expr__
        return False

    def __ne__(self, x):
        return not self == x

    def __repr__(self):
        return f"{self.__class__.__name__}({self!s})"

    def __str__(self):
        return str(self.__expr__)

    def __hash__(self):
        return hash(self.__expr__)

    def __reduce__(self):
        return self.__class__, (self.__expr__,)

    @abstractmethod
    def __eval__(self, o: _T_Obj):  # pragma: no cover
        raise NotImplementedError(f"{self.__class__.__name__}.__eval__datapath__()")

    # def __setattr__(self, name: str, value) -> None:
    #     if hasattr(self, "__expr__"):
    #         getattr(self, name)
    #         raise AttributeError(f"cannot set readonly attribute {name!r}")

    #     return super().__setattr__(name, value)


class Attribute(Expression[str, _T_Obj]):
    __slots__ = ()

    __evaluation_errors__ = (AttributeError,)

    def __eval__(self, o: _T_Obj):
        __tracebackhide__ = True
        return getattr(o, self.__expr__)

    def __str__(self):
        return f".{self.__expr__}"


class Item(Expression[_T_Item, _T_Obj]):
    __slots__ = ()

    __evaluation_errors__ = KeyError, IndexError

    def __eval__(self, o: _T_Obj):
        __tracebackhide__ = True
        return o[self.__expr__]

    def __str__(self):
        return f"[{self.__expr__!r}]"


class Slice(
    Expression[
        tuple[t.Union[_T_Item, None], t.Union[_T_Item, None], t.Union[_T_Item, None]],
        _T_Obj,
    ]
):

    __slots__ = ()

    __evaluation_errors__ = KeyError, IndexError

    def __eval__(self, o: _T_Obj):
        __tracebackhide__ = True
        return o[slice(*self.__expr__)]

    def __str__(self):
        start, stop, step = ("" if v is None else f"{v!r}" for v in self.__expr__)
        return f"[{start}:{stop}:{step}]"


class Call(Expression[tuple[_T_Args, _T_Kwargs], _T_Obj]):
    __slots__ = ()

    __evaluation_errors__ = (CallEvaluationError,)

    def __eval__(self, o: _T_Obj):
        __tracebackhide__ = True
        args, kwargs = self.__expr__
        try:
            return o(*args, **kwargs)
        except TypeError as e:
            if isinstance(o, Callable):
                raise

            raise CallEvaluationError(e) from e

    def __str__(self):
        args, kwargs = self.__expr__
        a = ", ".join(map(repr, args))
        kw = ", ".join(f"{k!s}={v!r}" for k, v in kwargs.items())
        return f'({", ".join(filter(None, (a, kw)))})'


class Lookup(Expression[tuple[Expression[t.Any, _T_Obj]], _T_Obj], t.Generic[_T_Obj]):
    """A chain of lookup experesions."""

    __slots__ = ("__expr__",)

    __offset__ = None

    __expr__: tuple[Expression[_T_Expr, _T_Obj]]

    def __new__(cls, *ops: Expression[_T_Expr, _T_Obj]):
        self = _object_new(cls)
        self.__setattr(__expr__=ops)
        return self

    @property
    def __ops__(self) -> None:
        return self.__expr__[self.__offset__ :]

    def __push__(self, *expr: Expression[_T_Expr, _T_Obj]):
        return self.__class__(*self.__expr__, *expr)

    def __getattr__(self, name: str):
        if name[:2] == "__" == name[-2:]:
            raise AttributeError(name)

        return self.__push__(Attribute(name))

    def __getitem__(self, k: t.Union[_T_Item, slice]):
        if k.__class__ is slice:
            return self.__push__(Slice((k.start, k.stop, k.step)))
        else:
            return self.__push__(Item(k))

    def __call__(self, *a: _T_Args, **kw: _T_Kwargs):
        return self.__push__(Call((a, FrozenDict(kw))))

    def __eval__(self, /, root: _T_Obj, start: int = None, stop: int = None):
        __tracebackhide__ = True
        val = root
        it = self.__ops__[start:stop]
        try:
            for t in it:
                val = t.__eval__(val)
        except EvaluationError:
            raise
        except Exception as e:
            raise EvaluationError.wrap(e) from e
        else:
            return val

    def __str__(self):
        return "<object>" + "".join(map(str, self.__expr__))

    def __iter__(self):
        return iter(self.__ops__)

    def __len__(self):
        return len(self.__expr__)

    # def __contains__(self, o):
    #     return o in self.__expr__

    def __reduce__(self):
        return self.__class__, self.__expr__


def look(expr: Lookup, /, root: _T_Obj, *, start: int = None, stop: int = None):
    return expr.__eval__(root, start=start, stop=stop)
