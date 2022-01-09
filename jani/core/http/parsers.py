import typing as t


from jani.common import json

from ninja.parser import Parser




class JSONParser(Parser):

    def parse_body(self, request):
        return json.loads(request.body)

