import typing as t 


from djx.common.utils import export
from pydantic.fields import FieldInfo




from ..common import ParamType


@export()
class ParamFieldInfo(FieldInfo):
    
    _paramtype: t.ClassVar[ParamType] = ParamType.any()

    __slots__ = 'paramtype',

    def __init__(
        self,
        default: t.Any,
        *,
        alias: str = None,
        title: str = None,
        description: str = None,
        gt: float = None,
        ge: float = None,
        lt: float = None,
        le: float = None,
        min_length: int = None,
        max_length: int = None,
        regex: str = None,
        deprecated: bool = None,
        # param_name: str = None,
        # param_type: Any = None,
        **extra: t.Any,
    ):
        # self.deprecated = deprecated
        # self.param_name: str = None
        # self.param_type: Any = None
        # self.model_field: t.Optional[ModelField] = None
        super().__init__(
            default,
            alias=alias,
            title=title,
            description=description,
            gt=gt,
            ge=ge,
            lt=lt,
            le=le,
            min_length=min_length,
            max_length=max_length,
            regex=regex,
            **extra,
        )

    # @classmethod
    # def _in(cls) -> str:
    #     "Openapi param.in value"
    #     return cls.__name__.lower()


@export()
class PathFieldInfo(ParamFieldInfo):
    _paramtype: t.ClassVar[ParamType] = ParamType.path



@export()
class QueryFieldInfo(ParamFieldInfo):
    _paramtype: t.ClassVar[ParamType] = ParamType.query


@export()
class HeaderFieldInfo(ParamFieldInfo):
    _paramtype: t.ClassVar[ParamType] = ParamType.header


@export()
class CookieFieldInfo(ParamFieldInfo):
    _paramtype: t.ClassVar[ParamType] = ParamType.cookie


@export()
class BodyFieldInfo(ParamFieldInfo):
    _paramtype: t.ClassVar[ParamType] = ParamType.body


@export()
class FormFieldInfo(ParamFieldInfo):
    _paramtype: t.ClassVar[ParamType] = ParamType.form


@export()
class FileFieldInfo(ParamFieldInfo):
    _paramtype: t.ClassVar[ParamType] = ParamType.file
