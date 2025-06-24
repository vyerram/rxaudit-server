from django.apps import AppConfig
from django.core.cache import cache
from django.db.models import F


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "core"
