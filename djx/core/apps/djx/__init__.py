# -*- coding: utf-8 -*-
from django.apps import AppConfig


class DjxApp(AppConfig):
    name = __name__

    def ready(self) -> None:
        print(f'DJX READY {self.label} @ {self.name} | {self.module.__name__}')