from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"address", views.Addressviewset, basename="address")
router.register(r"person", views.Personviewset, basename="person")


urls = []
urlpatterns = router.urls + urls
