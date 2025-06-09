import uuid
from django.conf import settings
from django.db import models
from typing import Type


class CoreModel(models.Model):

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, unique=True
    )
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    deleted_at = models.DateTimeField(editable=False, null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        related_query_name="%(class)s_created_by",
        null=True,
        blank=True,
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        related_query_name="%(class)s_updated_by",
        null=True,
        blank=True,
        editable=False,
    )

    class Meta:
        abstract = True


class CoreLookupModel(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, unique=True
    )
    code = models.CharField(max_length=20, blank=True, null=False)
    description = models.CharField(max_length=200, blank=True, null=False)

    class Meta:
        abstract = True

    def __str__(self):
        return self.description


def get_related_fields(model, core_fields):
    auto_relations = []
    direct_relations = []
    for field in model._meta.get_fields():
        if field.is_relation and field.name not in core_fields:
            (
                auto_relations.append(field.name)
                if field.auto_created
                else direct_relations.append(field.name)
            )

    return auto_relations, direct_relations


def get_query_set(model: Type[models.Model], core_fields: list):
    # auto_relations, direct_relations = get_related_fields(model, core_fields)
    # relations = tuple(auto_relations + direct_relations)
    # if len(direct_relations) > 0 and len(auto_relations) > 0:
    #     return (
    #         model.objects.select_related(*direct_relations)
    #         .prefetch_related(*auto_relations)
    #         .all()
    #     ), relations
    # elif len(direct_relations) > 0 and len(auto_relations) == 0:
    #     return model.objects.select_related(*direct_relations).all(), relations
    # elif len(auto_relations) > 0 and len(direct_relations) == 0:
    #     return model.objects.prefetch_related(*auto_relations).all(), relations
    # else:
    return model.objects.all(), ()


class Tabletype(CoreLookupModel):
    class Meta:
        db_table = "LKP_TTP_TableType"


class Tablegroup(CoreLookupModel):
    class Meta:
        db_table = "SET_TGP_TableGroup"


class Tablename(CoreModel):
    name = models.CharField(db_column="tnm_name", max_length=128)
    prefix = models.CharField(db_column="tnm_prefix", max_length=128)
    type = models.ForeignKey(
        "Tabletype",
        on_delete=models.PROTECT,
        db_column="tnm_type",
        related_name="tablename_type_tabletype_id",
        blank=True,
        null=True,
        to_field="id",
    )
    group = models.ForeignKey(
        "Tablegroup",
        on_delete=models.PROTECT,
        db_column="tnm_group",
        related_name="tablename_group_tablegroup_id",
        blank=True,
        null=True,
        to_field="id",
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "SET_TNM_TableName"


class Tableattribute(CoreModel):
    table_name = models.ForeignKey(
        Tablename,
        related_name="tablename_table_name_tableattribute_id",
        on_delete=models.PROTECT,
        db_column="tat_table_name",
        to_field="id",
    )
    attrib_name = models.CharField(db_column="tat_attrib_name", max_length=128)
    constraint = models.CharField(
        db_column="tat_constraint", max_length=128, blank=True, null=True
    )
    desc = models.TextField(db_column="tat_desc", blank=True, null=True)
    position = models.IntegerField(db_column="tat_position", blank=True, null=True)
    is_nullable = models.BooleanField(
        db_column="tat_is_nullable", blank=True, null=True
    )
    char_max_length = models.IntegerField(
        db_column="tat_char_max_len", blank=True, null=True
    )
    numeric_precision = models.IntegerField(
        db_column="tat_numeric_precision", blank=True, null=True
    )
    is_identity = models.BooleanField(
        db_column="tat_is_identity", blank=True, null=True
    )
    identity_generation = models.IntegerField(
        db_column="tat_identity_generation", blank=True, null=True
    )
    identity_start = models.IntegerField(
        db_column="tat_identity_start", blank=True, null=True
    )
    identity_increment = models.IntegerField(
        db_column="tat_identity_increment", blank=True, null=True
    )
    comment = models.CharField(
        db_column="tat_comment", max_length=128, blank=True, null=True
    )
    attrib_code = models.CharField(
        db_column="tat_attrib_code", max_length=128, blank=True, null=True
    )
    data_type = models.ForeignKey(
        "Attributetype",
        on_delete=models.PROTECT,
        db_column="tat_data_type",
        related_name="tableattribute_data_type_attributetype_id",
        blank=True,
        null=True,
        to_field="id",
    )
    default_value = models.BooleanField(
        db_column="tat_default_value", blank=True, null=True
    )

    class Meta:
        db_table = "SET_TAT_TableAttribute"

    def __str__(self):
        return self.attrib_name


class Tablerelationship(CoreModel):
    attr1 = models.CharField(
        db_column="trp_attr1", max_length=128, blank=True, null=True
    )
    attr2 = models.CharField(
        db_column="trp_attr2", max_length=128, blank=True, null=True
    )
    attr3 = models.CharField(
        db_column="trp_attr3", max_length=128, blank=True, null=True
    )
    relation_table_1 = models.ForeignKey(
        Tablename,
        on_delete=models.PROTECT,
        db_column="trp_relation_table_1",
        related_name="tablerelationship_relation_table_1_tablename_id",
        blank=True,
        null=True,
        to_field="id",
    )
    relation_column_1 = models.ForeignKey(
        Tableattribute,
        on_delete=models.PROTECT,
        db_column="trp_relation_column_1",
        related_name="tablerelationship_relation_column_1_tableattribute_id",
        blank=True,
        null=True,
        to_field="id",
    )
    relation_table_2 = models.ForeignKey(
        Tablename,
        on_delete=models.PROTECT,
        db_column="trp_relation_table_2",
        related_name="tablerelationship_relation_table_2_tablename_id",
        blank=True,
        null=True,
        to_field="id",
    )
    relation_column_2 = models.ForeignKey(
        Tableattribute,
        on_delete=models.PROTECT,
        db_column="trp_relation_column_2",
        related_name="tablerelationship_relation_column_2_tableattribute_id",
        blank=True,
        null=True,
        to_field="id",
    )
    type = models.ForeignKey(
        "Keytype",
        on_delete=models.PROTECT,
        db_column="trp_type",
        related_name="tablerelationship_type_keytype_id",
        blank=True,
        null=True,
        to_field="id",
    )
    ui_display = models.BooleanField(db_column="trp_ui_display", blank=True, null=True)
    reverse_display = models.BooleanField(
        db_column="trp_reverse_display", blank=True, null=True
    )

    class Meta:
        db_table = "SET_TRP_TableRelationship"


class Attributetype(CoreLookupModel):
    class Meta:
        db_table = "LKP_ATP_AttributeType"


class Keytype(CoreLookupModel):
    class Meta:
        db_table = "LKP_KTP_KeyType"
