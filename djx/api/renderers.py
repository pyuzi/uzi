import typing as t 

from djx.di import ioc


from djx.common import json


_T_Data = t.TypeVar('_T_Data')

class Renderer(t.Generic[_T_Data]):
    """
    All renderers should extend this class, setting the `media_type`
    and `format` attributes, and override the `.render()` method.
    """
    media_type: str = None
    format = None
    charset: str = 'utf-8'
    render_style = 'text'

    def render(self, data: _T_Data, accepted_media_type=None, renderer_context=None):
        raise NotImplementedError('Renderer class requires .render() to be implemented')



@ioc.alias(Renderer)
@ioc.injectable(cache=True)
class JSONRenderer(Renderer):
    """
    Renderer which serializes to JSON.
    """
    media_type = 'application/json'
    format = 'json'
    # encoder_class = encoders.JSONEncoder
    # ensure_ascii = not api_settings.UNICODE_JSON
    # compact = api_settings.COMPACT_JSON
    # strict = api_settings.STRICT_JSON

    # We don't set a charset because JSON is a binary encoding,
    # that can be encoded as utf-8, utf-16 or utf-32.
    # See: https://www.ietf.org/rfc/rfc4627.txt
    # Also: http://lucumr.pocoo.org/2013/7/19/application-mimetypes-and-encodings/
    charset = None

    # def get_indent(self, accepted_media_type, renderer_context):
    #     if accepted_media_type:
    #         # If the media type looks like 'application/json; indent=4',
    #         # then pretty print the result.
    #         # Note that we coerce `indent=0` into `indent=None`.
    #         base_media_type, params = parse_header(accepted_media_type.encode('ascii'))
    #         try:
    #             return zero_as_none(max(min(int(params['indent']), 8), 0))
    #         except (KeyError, ValueError, TypeError):
    #             pass

    #     # If 'indent' is provided in the context, then pretty print the result.
    #     # E.g. If we're being called by the BrowsableAPIRenderer.
    #     return renderer_context.get('indent', None)

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Render `data` into JSON, returning a bytestring.
        """
        if data is None:
            return b''
        else:
            return  json.dumps(data)
        
        