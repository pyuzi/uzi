
from django.contrib.staticfiles.handlers import StaticFilesHandler

from django.contrib.staticfiles.management.commands.runserver import (
    Command as RunserverCommand,
)

from django.conf import settings

from djx.di import ioc



class Command(RunserverCommand):
    
    help = "Starts a lightweight Web server for development and also serves static files."

    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        settings.IS_SETUP = False

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--async', action="store_true", dest='async_mode',
            help='Run in async mode.',
        )

    # def get_handler(self, *args, **options):
    #     """
    #     Return the static files serving handler wrapping the default handler,
    #     if static files should be served. Otherwise return the default handler.
    #     """
    #     handler = ioc.get(WS)
    #     handler = super().get_handler(*args, **options)
    #     use_static_handler = options['use_static_handler']
    #     insecure_serving = options['insecure_serving']
    #     if use_static_handler and (settings.DEBUG or insecure_serving):
    #         return StaticFilesHandler(handler)
    #     return handler
    