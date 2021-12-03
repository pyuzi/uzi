
import typing as t 

from http.client import responses

from django.template.response import SimpleTemplateResponse

from .types import HttpStatus

if t.TYPE_CHECKING:
    from .renderers import Renderer



_T_Data = t.TypeVar('_T_Data', covariant=True)



class Response(SimpleTemplateResponse, t.Generic[_T_Data]):
    """
    An HttpResponse that allows its data to be rendered into
    arbitrary media types.
    """

    data: _T_Data

    accepted_renderer: t.Optional['Renderer'] = None
    accepted_media_type: t.Optional[str] = None

    default_status: HttpStatus = HttpStatus.OK_200

    def __init__(self, data=..., status=None,
                 template_name=None, headers=None,
                 exception=False, content_type=None):
        """
        Alters the init arguments slightly.
        For example, drop 'template_name', and instead use 'data'.

        Setting 'renderer' and 'media_type' will typically be deferred,
        For example being set automatically by the `APIView`.
        """
        super().__init__(None)

        if data is not ...:
            self.data = data

        self.template_name = template_name
        self.exception = exception
        self.content_type = content_type

        if headers:
            for name, value in headers.items():
                self[name] = value
        
        self.status_code = status

    @property
    def status_code(self) -> HttpStatus:
        try:
            return self.__dict__['status_code']
        except KeyError:
            return self.__dict__.setdefault('status_code', HttpStatus(self.default_status))
    
    @status_code.setter
    def status_code(self, val: HttpStatus):
        if val is None:
            self.__dict__['status_code'] = HttpStatus(self.default_status)
        else:
            self.__dict__['status_code'] = HttpStatus(val)

    @property
    def rendered_content(self):

        renderer = self.accepted_renderer
        accepted_media_type = self.accepted_media_type
        context = getattr(self, 'renderer_context', None)

        assert renderer, ".accepted_renderer not set on Response"
        assert accepted_media_type, ".accepted_media_type not set on Response"
        # assert context is not None, ".renderer_context not set on Response"
        # context['response'] = self

        media_type = renderer.media_type
        charset = renderer.charset
        content_type = self.content_type

        if content_type is None and charset is not None:
            content_type = "{}; charset={}".format(media_type, charset)
        elif content_type is None:
            content_type = media_type
        self['Content-Type'] = content_type

        ret = renderer.render(self.data, accepted_media_type, context)
        if isinstance(ret, str):
            assert charset, (
                'renderer returned unicode, and did not specify '
                'a charset value.'
            )
            return ret.encode(charset)

        if not ret:
            del self['Content-Type']

        return ret

    @property
    def status_text(self):
        """
        Returns reason text corresponding to our HTTP response status code.
        Provided for convenience.
        """
        return responses.get(self.status_code, '')

    @property
    def is_empty(self):
        return not hasattr(self, 'data')

    def __getstate__(self):
        """
        Remove attributes from the response that shouldn't be cached.
        """
        state = super().__getstate__()
        for key in (
            'accepted_renderer', 'renderer_context', 'resolver_match',
            'client', 'request', 'json', 'wsgi_request'
        ):
            if key in state:
                del state[key]
        state['_closable_objects'] = []
        return state
