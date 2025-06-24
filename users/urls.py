from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views
from .cache import load_access_cache

router = DefaultRouter()
router.register(r"userrole", views.Userroleviewset, basename="userrole")
router.register(
    r"roleaccesscontrol", views.RoleAccessControlviewset, basename="roleaccesscontrol"
)
router.register(r"", views.Userviewset, basename="user")

urls = []
urlpatterns = router.urls + urls
load_access_cache()
