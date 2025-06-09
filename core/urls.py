"""
URL configuration for Aspyr project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from django.conf import settings
from rest_framework import permissions

from . import views
from .views import (
    login,
    get_retrieve_api_data,
    request_otp,
    verify_otp,
    reset_password,
    mfa_request_otp,
    mfa_verify_otp,
)
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from .cache import load_core_cache

router = DefaultRouter()
router.register(r"keytype", views.Keytypeviewset, basename="keytype")

router.register(r"attributetype", views.Attributetypeviewset, basename="attributetype")
router.register(r"tabletype", views.Tabletypeviewset, basename="tabletype")
router.register(
    r"tablerelationship", views.Tablerelationshipviewset, basename="tablerelationship"
)
router.register(r"tablegroup", views.Tablegroupviewset, basename="tablegroup")
router.register(
    r"tableattribute", views.Tableattributeviewset, basename="tableattribute"
)
router.register(r"tablename", views.Tablenameviewset, basename="tablename")

schema_view = get_schema_view(
    openapi.Info(
        title="Aspyr API",
        default_version="v1",
        description="Aspyr API description",
        terms_of_service="https://www.example.com/terms/",
        contact=openapi.Contact(email="contact@example.com"),
        license=openapi.License(name="Awesome License"),
    ),
    public=True,
    permission_classes=(permissions.IsAuthenticated,),
)
apps = settings.SYSTEM_APPS + settings.BASE_APPS
apps.remove("core")
system_urls = [path(rf"{app}/", include(rf"{app}.urls")) for app in apps]

urlpatterns = (
    router.urls
    + staticfiles_urlpatterns()
    + system_urls
    + [
        path(
            "swagger/",
            schema_view.with_ui("swagger", cache_timeout=0),
            name="schema-swagger-ui",
        ),
        path(
            "redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"
        ),
        path("admin/", admin.site.urls),
        path("login/", login),
        path("get_retrieve_api_data/", get_retrieve_api_data),
        path("request_otp/", request_otp, name="request_otp"),
        path("verify_otp/", verify_otp, name="verify_otp"),
        path("reset_password/", reset_password, name="reset_password"),
        path("mfa_request_otp/", mfa_request_otp, name="mfa_request_otp"),
        path("mfa_verify_otp/", mfa_verify_otp, name="mfa_verify_otp"),
    ]
)

load_core_cache()
