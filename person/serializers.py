from rest_framework import serializers
from core.serializers import CoreSerializer
from . import models


class Personserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.Person
        relations = []


class Addressserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.Address
        relations = []
