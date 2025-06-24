from django.apps import apps
from django.core.cache import cache
from django.db.models.functions import Lower


def load_access_cache():
    try:
        RoleAccessControl = apps.get_model("users", "RoleAccessControl")
        access_data = {}
        role_access_objs = (
            RoleAccessControl.objects.select_related(
                "role", "access_control", "access_type"
            )
            .annotate(access_name_lower=Lower("access_control__access_name"))
            .all()
        )

        if len(role_access_objs) == 0:
            return None
        role_access_records = role_access_objs.values(
            "role__name", "access_name_lower", "access_type__code"
        )

        for rec in role_access_records:
            if rec["role__name"] not in access_data.keys():
                access_data[rec["role__name"]] = {}
            access_data[rec["role__name"]][rec["access_name_lower"]] = rec[
                "access_type__code"
            ]

        cache.set("access_data", access_data)
    except Exception as e:
        print(e)
