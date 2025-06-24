from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.core.cache import cache
from users.utils import create_access_controls
from django.db.models.functions import Lower


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "users"

    def ready(self):
        post_migrate.connect(create_access_controls, sender=self)
