from rest_framework.serializers import ModelSerializer
from drf_queryfields import QueryFieldsMixin
from django.forms.models import model_to_dict
import types
from functools import lru_cache

from rest_framework import serializers
from functools import partial
from core.utils import get_app_name_for_model, get_custom_serializer_class
from . import models


class CoreSerializer(QueryFieldsMixin, ModelSerializer):

    def get_serializer_class(self, relation, serializer_fields, serializer):
        model = serializer.Meta.model
        model_relation = model._meta.get_field(relation)
        if model_relation.is_relation:
            serializer_class = model_serializer(model_relation.related_model, ())
            if serializer_class:
                method_name = "get_" + relation
                serializer_fields[relation] = serializers.SerializerMethodField()
                if model_relation.many_to_many or model_relation.one_to_many:

                    retrieve_data_for_many_relation.__name__ = method_name
                    setattr(
                        type(serializer),
                        method_name,
                        partial(
                            retrieve_data_for_many_relation, {"relation": relation}
                        ),
                    )
                elif model_relation.one_to_one or model_relation.many_to_one:
                    retrieve_data_for_one_relation.__name__ = method_name
                    setattr(
                        type(serializer),
                        method_name,
                        partial(retrieve_data_for_one_relation, {"relation": relation}),
                    )

    def get_fields(self):
        fields = super().get_fields()
        if self.Meta and hasattr(self.Meta, "relations") and self.Meta.relations:
            for relation in self.Meta.relations:
                if (relation not in fields.keys()) or (
                    "SerializerMethodField" not in str(type(fields[relation]))
                ):
                    self.get_serializer_class(relation, fields, self)
        return fields

    def get_object_id(self, obj, relation):
        rel_obj = getattr(obj, relation)
        if "create_reverse_many_to_one_manager" in str(type(rel_obj)):
            return rel_obj.last().id if rel_obj and rel_obj.last() else None
        return rel_obj.id if rel_obj else None

    def get_relation_fetch_type(self):
        nested_relation = False
        plain_relation = False
        only_id = False
        request = self.context.get("request")
        if request and getattr(request, "query_params"):
            params = request.query_params

            if "nested_relation" in params and bool(params["nested_relation"]):
                nested_relation = True
            elif "plain_relation" in params and bool(params["plain_relation"]):
                plain_relation = True
            else:
                only_id = True
        else:
            only_id = True
        return nested_relation, plain_relation, only_id

    def retrieve_relation_data(self, obj, relation):
        model = self.Meta.model
        model_relation = model._meta.get_field(relation)
        nested_relation, plain_relation, only_id = self.get_relation_fetch_type()
        if model_relation.is_relation:
            if nested_relation:
                related_entity = model_relation.remote_field.model.__name__
                serializer_class = get_custom_serializer_class(
                    get_app_name_for_model(related_entity), related_entity
                )
                if serializer_class:
                    if model_relation.many_to_many or model_relation.one_to_many:
                        # More and more I see it this logic is seeming bull shit. Need to come up with better logic
                        serializer_data = serializer_class(getattr(obj, relation).all())
                        return serializer_data.data
                    elif model_relation.one_to_one or model_relation.many_to_one:
                        serializer_data = serializer_class(getattr(obj, relation))
                        return serializer_data.data
                else:
                    return self.get_object_id(obj, relation)
            elif plain_relation:
                if model_relation.many_to_many or model_relation.one_to_many:
                    related_manager = getattr(obj, relation)
                    data = [rec for rec in related_manager.all().values()]
                    return data
                elif model_relation.one_to_one or model_relation.many_to_one:
                    related_obj = getattr(obj, relation)
                    if related_obj:
                        return model_to_dict(getattr(obj, relation))
            elif only_id:
                return self.get_object_id(obj, relation)

    class Meta:
        fields = "__all__"
        abstract = True


def retrieve_data_for_one_relation(self, obj):
    return model_to_dict(getattr(obj, self["relation"]))


def retrieve_data_for_many_relation(self, obj):
    related_manager = getattr(obj, self["relation"])
    data = [rec for rec in related_manager.all().values()]
    return data


@lru_cache
def model_serializer(model, relations):
    custom_serializer = get_custom_serializer_class(
        model._meta.app_label, model.__class__.__name__
    )
    if not custom_serializer:
        meta_class = types.new_class("Meta", (CoreSerializer.Meta,), {})
        setattr(meta_class, "model", model)
        setattr(meta_class, "relations", relations)
        result = types.new_class(model.__name__ + "Serializer", (CoreSerializer,), {})
        setattr(result, "Meta", meta_class)
        return result


class Tablenameserializer(CoreSerializer):
    tabletype = serializers.SerializerMethodField()
    tablegroup = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.Tablename
        relations = []

    def get_tabletype(self, obj):
        return super().retrieve_relation_data(obj, "tabletype")

    def get_tablegroup(self, obj):
        return super().retrieve_relation_data(obj, "tablegroup")


class Tableattributeserializer(CoreSerializer):
    attributetype = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.Tableattribute
        relations = []

    def get_attributetype(self, obj):
        return super().retrieve_relation_data(obj, "attributetype")


class Tablegroupserializer(CoreSerializer):
    tablename = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.Tablegroup
        relations = []

    def get_tablename(self, obj):
        return super().retrieve_relation_data(obj, "tablename")


class Tablerelationshipserializer(CoreSerializer):
    tablename = serializers.SerializerMethodField()
    tableattribute = serializers.SerializerMethodField()
    keytype = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.Tablerelationship
        relations = []

    def get_tablename(self, obj):
        return super().retrieve_relation_data(obj, "tablename")

    def get_tableattribute(self, obj):
        return super().retrieve_relation_data(obj, "tableattribute")

    def get_keytype(self, obj):
        return super().retrieve_relation_data(obj, "keytype")


class Tabletypeserializer(CoreSerializer):
    tablename = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.Tabletype
        relations = []

    def get_tablename(self, obj):
        return super().retrieve_relation_data(obj, "tablename")


class Attributetypeserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.Attributetype
        relations = []


class Keytypeserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.Keytype
        relations = []
