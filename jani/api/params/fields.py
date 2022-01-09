import typing as t 

from collections.abc import Iterable, Callable, Mapping, Hashable

from jani.common.functools import export
from jani.common.collections import orderedset
from jani.di import Injectable
from pydantic.fields import FieldInfo

from .. import abc


from .core import T_ParamDataType


@export()
class ParamFieldInfo(FieldInfo):

    __slots__ = 'param_src',

    param_src: tuple[Injectable, Hashable]

    @t.overload
    def __init__(
        self,
        default: t.Any=...,
        *,
        source: T_ParamDataType,
        default_factory: t.Union[Callable[[], t.Any], None] = None,
        alias: t.Union[str, None] = None,
        title: t.Union[str, None] = None,
        description: t.Union[str, None] = None,
        const: t.Union[bool, None] = None,
        gt: t.Union[float, None] = None,
        ge: t.Union[float, None] = None,
        lt: t.Union[float, None] = None,
        le: t.Union[float, None] = None,
        multiple_of: t.Union[float, None] = None,
        min_items: t.Union[int, None] = None,
        max_items: t.Union[int, None] = None,
        min_length: t.Union[int, None] = None,
        max_length: t.Union[int, None] = None,
        regex: t.Union[str, None] = None,
        deprecated: t.Union[bool, None] = None,
        **extra: t.Any,
    ):...

    def __init__(self, 
                default: t.Any = ..., *,
                source: T_ParamDataType, 
                **kwargs: t.Any) -> None:
        super().__init__(default=default, **kwargs)

        if isinstance(source, (list, tuple)):
            if 0 < len(source) < 3:
                source, aka, *_ = *source, self.alias or ...
            else:
                raise ValueError(f'param scource {source.__class__.__name__} must 1 or 2 items not {len(source)}')
        else:
            aka = self.alias or ...
            
        self.param_src = source, aka





@t.overload
def Param(
        default: t.Any=...,
        source: T_ParamDataType = None,
        *,
        default_factory: t.Union[Callable[[], t.Any], None] = None,
        alias: t.Union[str, None] = None,
        title: t.Union[str, None] = None,
        description: t.Union[str, None] = None,
        const: t.Union[bool, None] = None,
        gt: t.Union[float, None] = None,
        ge: t.Union[float, None] = None,
        lt: t.Union[float, None] = None,
        le: t.Union[float, None] = None,
        multiple_of: t.Union[float, None] = None,
        min_items: t.Union[int, None] = None,
        max_items: t.Union[int, None] = None,
        min_length: t.Union[int, None] = None,
        max_length: t.Union[int, None] = None,
        regex: t.Union[str, None] = None,
        deprecated: t.Union[bool, None] = None,
        **extra: t.Any) -> ParamFieldInfo:
    ...

@export()
def Param(default=..., source=None, **kwds):
    return ParamFieldInfo(default, source=source or abc.Params, **kwds)





@t.overload
def Path(
        default: t.Any=...,
        *,
        default_factory: t.Union[Callable[[], t.Any], None] = None,
        alias: t.Union[str, None] = None,
        title: t.Union[str, None] = None,
        description: t.Union[str, None] = None,
        const: t.Union[bool, None] = None,
        gt: t.Union[float, None] = None,
        ge: t.Union[float, None] = None,
        lt: t.Union[float, None] = None,
        le: t.Union[float, None] = None,
        multiple_of: t.Union[float, None] = None,
        min_items: t.Union[int, None] = None,
        max_items: t.Union[int, None] = None,
        min_length: t.Union[int, None] = None,
        max_length: t.Union[int, None] = None,
        regex: t.Union[str, None] = None,
        deprecated: t.Union[bool, None] = None,
        **extra: t.Any) -> ParamFieldInfo:
    ...

@export()
def Path(default=..., **kwds):
    return Param(default, abc.Kwargs, **kwds)



@t.overload
def Query(
        default: t.Any=...,
        *,
        default_factory: t.Union[Callable[[], t.Any], None] = None,
        alias: t.Union[str, None] = None,
        title: t.Union[str, None] = None,
        description: t.Union[str, None] = None,
        const: t.Union[bool, None] = None,
        gt: t.Union[float, None] = None,
        ge: t.Union[float, None] = None,
        lt: t.Union[float, None] = None,
        le: t.Union[float, None] = None,
        multiple_of: t.Union[float, None] = None,
        min_items: t.Union[int, None] = None,
        max_items: t.Union[int, None] = None,
        min_length: t.Union[int, None] = None,
        max_length: t.Union[int, None] = None,
        regex: t.Union[str, None] = None,
        deprecated: t.Union[bool, None] = None,
        **extra: t.Any) -> ParamFieldInfo:
    ...

@export()
def Query(default=..., **kwds):
    return Param(default, abc.Query, **kwds)



@t.overload
def Body(
        default: t.Any=...,
        *,
        default_factory: t.Union[Callable[[], t.Any], None] = None,
        alias: t.Union[str, None] = None,
        title: t.Union[str, None] = None,
        description: t.Union[str, None] = None,
        const: t.Union[bool, None] = None,
        gt: t.Union[float, None] = None,
        ge: t.Union[float, None] = None,
        lt: t.Union[float, None] = None,
        le: t.Union[float, None] = None,
        multiple_of: t.Union[float, None] = None,
        min_items: t.Union[int, None] = None,
        max_items: t.Union[int, None] = None,
        min_length: t.Union[int, None] = None,
        max_length: t.Union[int, None] = None,
        regex: t.Union[str, None] = None,
        deprecated: t.Union[bool, None] = None,
        **extra: t.Any) -> ParamFieldInfo:
    ...

@export()
def Body(default=..., **kwds):
    return Param(default, abc.Body, **kwds)



@t.overload
def Form(
        default: t.Any=...,
        *,
        default_factory: t.Union[Callable[[], t.Any], None] = None,
        alias: t.Union[str, None] = None,
        title: t.Union[str, None] = None,
        description: t.Union[str, None] = None,
        const: t.Union[bool, None] = None,
        gt: t.Union[float, None] = None,
        ge: t.Union[float, None] = None,
        lt: t.Union[float, None] = None,
        le: t.Union[float, None] = None,
        multiple_of: t.Union[float, None] = None,
        min_items: t.Union[int, None] = None,
        max_items: t.Union[int, None] = None,
        min_length: t.Union[int, None] = None,
        max_length: t.Union[int, None] = None,
        regex: t.Union[str, None] = None,
        deprecated: t.Union[bool, None] = None,
        **extra: t.Any) -> ParamFieldInfo:
    ...

@export()
def Form(default=..., **kwds):
    return Param(default, abc.Form, **kwds)



@t.overload
def Input(
        default: t.Any=...,
        *,
        default_factory: t.Union[Callable[[], t.Any], None] = None,
        alias: t.Union[str, None] = None,
        title: t.Union[str, None] = None,
        description: t.Union[str, None] = None,
        const: t.Union[bool, None] = None,
        gt: t.Union[float, None] = None,
        ge: t.Union[float, None] = None,
        lt: t.Union[float, None] = None,
        le: t.Union[float, None] = None,
        multiple_of: t.Union[float, None] = None,
        min_items: t.Union[int, None] = None,
        max_items: t.Union[int, None] = None,
        min_length: t.Union[int, None] = None,
        max_length: t.Union[int, None] = None,
        regex: t.Union[str, None] = None,
        deprecated: t.Union[bool, None] = None,
        **extra: t.Any) -> ParamFieldInfo:
    ...

@export()
def Input(default=..., **kwds):
    return Param(default, abc.Inputs, **kwds)



@t.overload
def File(
        default: t.Any=...,
        *,
        default_factory: t.Union[Callable[[], t.Any], None] = None,
        alias: t.Union[str, None] = None,
        title: t.Union[str, None] = None,
        description: t.Union[str, None] = None,
        const: t.Union[bool, None] = None,
        gt: t.Union[float, None] = None,
        ge: t.Union[float, None] = None,
        lt: t.Union[float, None] = None,
        le: t.Union[float, None] = None,
        multiple_of: t.Union[float, None] = None,
        min_items: t.Union[int, None] = None,
        max_items: t.Union[int, None] = None,
        min_length: t.Union[int, None] = None,
        max_length: t.Union[int, None] = None,
        regex: t.Union[str, None] = None,
        deprecated: t.Union[bool, None] = None,
        **extra: t.Any) -> ParamFieldInfo:
    ...

@export()
def File(default=..., **kwds):
    return Param(default, abc.Files, **kwds)




@t.overload
def Cookie(
        default: t.Any=...,
        *,
        default_factory: t.Union[Callable[[], t.Any], None] = None,
        alias: t.Union[str, None] = None,
        title: t.Union[str, None] = None,
        description: t.Union[str, None] = None,
        const: t.Union[bool, None] = None,
        gt: t.Union[float, None] = None,
        ge: t.Union[float, None] = None,
        lt: t.Union[float, None] = None,
        le: t.Union[float, None] = None,
        multiple_of: t.Union[float, None] = None,
        min_items: t.Union[int, None] = None,
        max_items: t.Union[int, None] = None,
        min_length: t.Union[int, None] = None,
        max_length: t.Union[int, None] = None,
        regex: t.Union[str, None] = None,
        deprecated: t.Union[bool, None] = None,
        **extra: t.Any) -> ParamFieldInfo:
    ...

@export()
def Cookie(default=..., **kwds):
    return Param(default, abc.Cookies, **kwds)


@t.overload
def Header(
        default: t.Any=...,
        *,
        default_factory: t.Union[Callable[[], t.Any], None] = None,
        alias: t.Union[str, None] = None,
        title: t.Union[str, None] = None,
        description: t.Union[str, None] = None,
        const: t.Union[bool, None] = None,
        gt: t.Union[float, None] = None,
        ge: t.Union[float, None] = None,
        lt: t.Union[float, None] = None,
        le: t.Union[float, None] = None,
        multiple_of: t.Union[float, None] = None,
        min_items: t.Union[int, None] = None,
        max_items: t.Union[int, None] = None,
        min_length: t.Union[int, None] = None,
        max_length: t.Union[int, None] = None,
        regex: t.Union[str, None] = None,
        deprecated: t.Union[bool, None] = None,
        **extra: t.Any) -> ParamFieldInfo:
    ...

@export()
def Header(default=..., **kwds):
    return Param(default, abc.Headers, **kwds)


