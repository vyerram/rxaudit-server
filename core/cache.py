from django.apps import AppConfig
from django.apps import apps
from django.core.cache import cache
from django.db.models import F
from django.conf import settings
from .constants import TableTypes, only_alphabets_regular_expression
import re


def load_core_cache():
    try:
        Tablename = apps.get_model(app_label="core", model_name="Tablename")
        system_data = {}
        table_objs = (
            Tablename.objects.select_related("type")
            .prefetch_related("tablename_table_name_tableattribute_id")
            .all()
        )
        if len(table_objs) == 0:
            return None
        records = table_objs.values(
            "name",
            attrib_name=F("tablename_table_name_tableattribute_id__attrib_name"),
            typec=F("type__code"),
        )
        from . import models, constants

        code_model_fields = [field.name for field in models.CoreModel._meta.fields]
        code_lookup_fields = [
            field.name for field in models.CoreLookupModel._meta.fields
        ]
        for rec in records:
            if rec["name"] in system_data.keys():
                system_data[rec["name"]].append(rec["attrib_name"])
            else:
                system_data[rec["name"]] = [rec["attrib_name"]]
                (
                    system_data[rec["name"]].extend(code_lookup_fields)
                    if constants.TableTypes.LookupTable.value == rec["typec"]
                    else system_data[rec["name"]].extend(code_model_fields)
                )

        cache.set("entity_data", system_data)
        load_lookup_cache()
    except Exception as e:
        print(e)


def load_lookup_cache():
    for appname in settings.SYSTEM_APPS + settings.BASE_APPS:
        app = apps.get_app_config(appname)
        for model in app.get_models():
            if model._meta.db_table.__contains__(TableTypes.LookupTable.value):
                query_set = model.objects.all()
                cachekey = re.sub(
                    only_alphabets_regular_expression, "", str(query_set.query)
                )
                cache.set(cachekey, query_set)
