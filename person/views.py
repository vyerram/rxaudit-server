from core.views import CoreViewset
from . import models, serializers


class Personviewset(CoreViewset):
    serializer_class = serializers.Personserializer
    queryset = models.Person.objects.all()


class Addressviewset(CoreViewset):
    serializer_class = serializers.Addressserializer
    queryset = models.Address.objects.all()
