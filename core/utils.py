import os
from url_filter.integrations.drf import DjangoFilterBackend
from importlib import import_module
from importlib.util import find_spec
from typing import Optional
from sqlalchemy import create_engine
from django.conf import settings
from pandas import isnull
from django.db.models import Q
import boto3
from django.contrib.contenttypes.models import ContentType
from botocore.exceptions import ClientError
from django.shortcuts import get_object_or_404
from django.http import Http404


class AllFieldsDjangoFilterBackend(DjangoFilterBackend):
    """
    Filters DRF views by any of the objects properties.
    """

    def get_filterset_class(self, view, queryset=None):
        """
        Return the `FilterSet` class used to filter the queryset.
        """
        filterset_class = getattr(view, "filterset_class", None)
        filterset_fields = getattr(view, "filterset_fields", None)

        if filterset_fields or filterset_class:
            return super().get_filterset_class(self, view, queryset)

        class AutoFilterSet(self.filterset_base):
            class Meta:
                model = queryset.model
                fields = "__all__"

        return AutoFilterSet


def get_foreign_key_rel_dict(fields):
    rels = {}
    for field in fields:
        if hasattr(field, "_related_name") and not rels.__contains__(
            field._related_name
        ):
            rels[field._related_name] = field.name

    return rels


def is_str_empty_or_none(val: str):
    return val is None or val == "" or val == -1 or isnull(val)


def get_default_value_if_null(real_value, default_value):
    return default_value if is_str_empty_or_none(real_value) else real_value


def get_object_or_none(model, *args, **kwargs):
    try:
        return get_object_or_404(model, *args, **kwargs)
    except Http404:
        return None


def get_sql_alchemy_conn():
    conn_engine = create_engine(
        f"postgresql+psycopg2://{settings.DB_CONN.username}:{settings.DB_CONN.password}@{settings.DB_CONN.hostname}/{settings.DB_CONN.path[1:]}"
    )

    return conn_engine


def cursor_result_to_response(result):
    if "Row" in str(type(result)):
        return result._asdict()
    if "CursorResult" in str(type(result)):
        return [r._asdict() for r in result]


def get_app_name_for_model(class_name: str):
    content_types = ContentType.objects.filter(model=class_name.lower())
    if len(content_types) > 0:
        content_type = content_types.first()
        return content_type.app_label if content_type else None


def get_custom_model_class(appname: str, class_name: str) -> Optional[str]:
    return __get_file_from_module(appname, class_name, "models")


def get_custom_view_class(appname: str, class_name: str) -> Optional[str]:
    return __get_file_from_module(appname, rf"{class_name}viewset", "views")


def get_custom_serializer_class(appname: str, class_name: str) -> Optional[str]:
    return __get_file_from_module(appname, rf"{class_name}serializer", "serializers")


def __get_file_from_module(
    appname: str, class_name: str, file_name: str
) -> Optional[str]:
    try:
        module = import_module(appname)
        if module and find_spec(rf"{appname}.{file_name}"):
            app_module = getattr(module, file_name)
            if hasattr(app_module, class_name):
                return getattr(app_module, class_name)
        else:
            return None
    except ImportError:
        return None
    except AttributeError:
        return None


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
        if model_field.get_internal_type().__contains__("ForeignKey"):  # YYYY-MM-DD
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
                            eac_rec[int_field], 0
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
            raise e
    model.objects.bulk_create(model_objs)


def get_boto3_client():
    session = boto3.Session(
        aws_access_key_id=settings.AWS_SERVER_ACCESS_KEY,
        aws_secret_access_key=settings.AWS_SERVER_SECRET_KEY,
        region_name=settings.AWS_SERVER_REGION,
    )
    s3_client = session.client("s3")
    return s3_client


def upload_file(file_path, file_url=None):
    s3_client = get_boto3_client()
    object_name = (
        file_url.replace(f"{settings.AWS_BUCKET}/", "")
        if file_url is not None
        else os.path.basename(file_path)
    )
    try:
        response = s3_client.upload_file(file_path, settings.AWS_BUCKET, object_name)
    except ClientError as e:
        print(e)


def download_file(file_path, file_url=None):
    if os.path.exists(file_path):
        return

    # Create parent directory if it doesn't exist
    parent_dir = os.path.dirname(file_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    s3_client = get_boto3_client()
    object_name = (
        file_url.replace(f"{settings.AWS_BUCKET}/", "")
        if file_url is not None
        else os.path.basename(file_path)
    )
    try:
        response = s3_client.download_file(settings.AWS_BUCKET, object_name, file_path)
    except ClientError as e:
        print(e)


def get_s3_file_location(bucket, object_name):
    try:
        s3_client = get_boto3_client()
        url = s3_client.generate_presigned_url(
            ClientMethod="get_object", Params={"Bucket": bucket, "Key": object_name}
        )
        return url
    except ClientError as e:
        print(e)
