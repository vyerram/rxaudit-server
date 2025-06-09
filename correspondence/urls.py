from django.urls import path
from correspondence import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
urls = [
    path("generate_pdf", views.generate_fillable_form_pdf, name="generate_pdf"),
]
urlpatterns = router.urls + urls
