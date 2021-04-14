from typing import Any, Protocol, Generic, TypeVar, runtime_checkable



_IK = TypeVar("_IK")
_IV = TypeVar("_IV")


class InjectorProto(Protocol[_IK, _IV]):

    def get(self, k: _IK) -> _IV:
        ...

    def __getitem__(self, k: _IK) -> _IV:
        ...

    def __contains__(self, k: _IK) -> bool:
        ...
