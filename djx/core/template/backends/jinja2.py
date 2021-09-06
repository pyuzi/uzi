import typing as t 
from pathlib import PurePath
from djx.di import di

import jinja2

from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.template.backends import utils

from django.template.backends.base import BaseEngine

from djx.core import settings
from djx.core.abc import Request
from djx.common.utils import cached_property
from djx.common.imports import ObjectImportRef

from jinja2 import Environment

from .. import RawTemplate


class Origin:
    """
    A container to hold debug information as described in the template API
    documentation.
    """
    
    __slots__ = 'name', 'template_name'

    def __init__(self, name, template_name):
        self.name = name
        self.template_name = template_name




class TemplateWrapper:
    
    __slots__ = 'template', 'backend', 'origin', '__weakref__'

    request: Request = di.injected_property(default=None)

    template: jinja2.Template
    backend: 'Jinja2'
    origin: Origin

    def __init__(self, template, backend):
        self.template = template
        self.backend = backend
        self.origin = Origin(
            name=template.filename, template_name=template.name,
        )

    def render(self, context=(), /, request=None, **kwds):
        if context is None:
            context = {}

        context = dict(context, **kwds)

        if request is None:
            request = self.request
        
        if request is not None:
            from . import utils
            context['request'] = request
            context['csrf_input'] = utils.csrf_input_lazy(request)
            context['csrf_token'] = utils.csrf_token_lazy(request)
            for context_processor in self.backend.template_context_processors:
                context.update(context_processor(request))
        try:
            return self.template.render(context)
        except jinja2.TemplateSyntaxError as exc:
            new = TemplateSyntaxError(exc.args)
            new.template_debug = get_exception_info(exc)
            raise new from exc






def get_exception_info(exception):
    """
    Format exception information for display on the debug page using the
    structure described in the template API documentation.
    """
    context_lines = 10
    lineno = exception.lineno
    source = exception.source
    if source is None:
        exception_file = PurePath(exception.filename)
        if exception_file.exists():
            with open(exception_file, 'r') as fp:
                source = fp.read()
    if source is not None:
        lines = list(enumerate(source.strip().split('\n'), start=1))
        during = lines[lineno - 1][1]
        total = len(lines)
        top = max(0, lineno - context_lines - 1)
        bottom = min(total, lineno + context_lines)
    else:
        during = ''
        lines = []
        total = top = bottom = 0
    return {
        'name': exception.filename,
        'message': exception.message,
        'source_lines': lines[top:bottom],
        'line': lineno,
        'before': '',
        'during': during,
        'after': '',
        'total': total,
        'top': top,
        'bottom': bottom,
    }



class RawLoader(jinja2.BaseLoader):

    def get_source(self, environment: Environment, template: t.Any) -> tuple[str, t.Optional[str], t.Optional[t.Callable[[], bool]]]:
        return super().get_source(environment, template)



# class Environment(jinja2.Environment):
#     ...


class Jinja2(BaseEngine):

    app_dirname = 'jinja2'

    env: jinja2.Environment

    template_wrapper = TemplateWrapper

    def __init__(self, params):
        params = params.copy()
        options = params.pop('OPTIONS').copy()
        super().__init__(params)

        self.context_processors = options.pop('context_processors', [])

        env = ObjectImportRef(options.pop('environment', 'jinja2.Environment'))

        if 'loader' not in options:
            options['loader'] = jinja2.FileSystemLoader(self.template_dirs)

        options.setdefault('autoescape', True)
        options.setdefault('auto_reload', settings.DEBUG)
        options.setdefault('undefined',
               jinja2.DebugUndefined if settings.DEBUG else jinja2.Undefined
            )
        
        self.env = di.make(env, **options)

    def wrap_template(self, template):
        return self.template_wrapper(template, self)

    def from_string(self, template_code):
        return self.wrap_template(self.env.from_string(template_code))

    def get_template(self, template_name):
        try:
            return self.wrap_template(self.env.get_template(template_name), self)
        except jinja2.TemplateNotFound as exc:
            raise TemplateDoesNotExist(exc.name, backend=self) from exc
        except jinja2.TemplateSyntaxError as exc:
            new = TemplateSyntaxError(exc.args)
            new.template_debug = get_exception_info(exc)
            raise new from exc

    @cached_property
    def template_context_processors(self):
        return [ObjectImportRef(path)() for path in self.context_processors]



