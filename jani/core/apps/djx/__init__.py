# -*- coding: utf-8 -*-

from django.apps import AppConfig



class DjxApp(AppConfig):
    name = __name__

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        from . import providers

    def ready(self) -> None:
        print(f'DJX READY {self.label} @ {self.name} | {self.module.__name__}')

        from jani.core.models.base import _prepare_pending_models
        _prepare_pending_models()



