import typing as t

from ninja.renderers import BaseRenderer

from jani.common import json
from jani.core.http import HttpRequest


class JSONRenderer(BaseRenderer):
    media_type = "application/json"
    json_dumps_opts: json.JsonOpt = 0
    json_dumps_default: t.Callable[[t.Any], json.Jsonable] = None

    def render(self, request: HttpRequest, data: t.Any, *, response_status: int):
        return json.dumps(data, self.json_dumps_default, self.json_dumps_opts)
