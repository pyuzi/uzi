# -*- coding: utf-8 -*-
from django.apps import AppConfig, apps


class DjxApp(AppConfig):
    name = __name__

    def ready(self) -> None:
        print(f'DJX READY {self.label} @ {self.name} | {self.module.__name__}')

        from djx.core.models.base import _prepare_pending_models
        _prepare_pending_models()
