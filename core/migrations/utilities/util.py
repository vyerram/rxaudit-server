from django.db.models import Q

from core.utils import get_default_value_if_null


def migrate_bulk_data(apps, appname: str, class_name: str, data: list) -> bool:
    model = apps.get_model(app_label=appname, model_name=class_name)
    model_objs = []
    qs = model.objects.all()
    int_fields = []
    rel_fields = {}
    for model_field in model._meta.get_fields():
        if model_field.get_internal_type().__contains__(
            "Integer"
        ) or model_field.get_internal_type().__contains__("Float"):
            int_fields.append(model_field.name)
        if model_field.get_internal_type().__contains__("ForeignKey"):
            rel_fields[model_field.name] = model_field.related_model
    if len(data) > 0:
        rels = {}
        fkeys = [s.split("__") for s in data[0].keys() if "__" in s]
        for s in data[0].keys():
            if "__" in s:
                rel_table, rel_field = s.split("__")
                if rel_table in rels:
                    rels[rel_table].append(rel_field)
                else:
                    rels[rel_table] = [rel_field]
    for eac_rec in data:
        try:
            for rel, fields in rels.items():
                Qr = None
                for field in fields:
                    q = Q(**{"%s__contains" % field: eac_rec[rf"{rel}__{field}"]})
                    if Qr:
                        Qr = Qr & q  # or & for filtering
                    else:
                        Qr = q

                rel_objs = rel_fields[rel].objects.filter(Qr)
                if len(rel_objs) > 0:
                    eac_rec[rel] = rel_objs.first()
                    for field in fields:
                        fkey = rf"{rel}__{field}"
                        del eac_rec[fkey]
                else:
                    for field in fields:
                        fkey = rf"{rel}__{field}"
                        if rel in eac_rec:
                            eac_rec[rel][field] = eac_rec[fkey]
                        else:
                            eac_rec[rel] = {field: eac_rec[fkey]}
                        del eac_rec[fkey]
            if len(int_fields) > 0:
                for int_field in int_fields:
                    if int_field in eac_rec:
                        eac_rec[int_field] = get_default_value_if_null(
                            int(eac_rec[int_field]), 0
                        )
            for rel in eac_rec.keys():
                if type(eac_rec[rel]) is dict and rel in rel_fields:
                    related_class = model._meta.get_field(rel).related_model
                    related_obj = related_class(**eac_rec[rel])
                    related_obj.save()
                    eac_rec[rel] = related_obj
            obj = model(**eac_rec)
            if obj not in qs:
                model_objs.append(obj)
        except Exception as e:
            print(e)
    model.objects.bulk_create(model_objs)


def reverse_migrated_bulk_data(apps, appname: str, class_name: str, data: list) -> bool:
    model = apps.get_model(app_label=appname, model_name=class_name)
    for eac_rec in data:
        record = model.objects.filter(**eac_rec)
        record.delete()
