# -*- coding: utf-8 -*-
from django.apps import AppConfig


class GurmerotaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gurmerota'

    def ready(self):
        from . import signals  # noqa: F401
