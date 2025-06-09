from .models import CoreModel
from django.contrib import admin
from django.conf import settings
from django.apps import apps

core_fields = [field.name for field in CoreModel._meta.fields]
core_fields.append("password")


class UniversalAdmin(admin.ModelAdmin):
    def get_list_display(self, request):
        return [
            field.name
            for field in self.model._meta.concrete_fields
            if field.name not in core_fields
        ]


for appname in settings.SYSTEM_APPS + settings.BASE_APPS:
    app = apps.get_app_config(appname)
    for model in app.get_models():
        if model.__name__ != "User":
            admin.site.register(model, UniversalAdmin)
