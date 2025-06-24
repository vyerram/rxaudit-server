from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(
    r"pharmacystatus", views.PharmacyStatusviewset, basename="pharmacystatus"
)
router.register(r"group", views.Groupviewset, basename="group")
router.register(r"volumegroup", views.VolumeGroupviewset, basename="volumegroup")
router.register(
    r"groupsalesinfo", views.GroupSalesInfoviewset, basename="groupsalesinfo"
)
router.register(
    r"volumegroupsalesinfo",
    views.VolumeGroupSalesInfoviewset,
    basename="volumegroupsalesinfo",
)
router.register(
    r"pharmacysalesinfo", views.PharmacySalesInfoviewset, basename="pharmacysalesinfo"
)
router.register(r"pharmacy", views.Pharmacyviewset, basename="pharmacy")
router.register(r"rebateinfo", views.RebateInfoviewset, basename="rebateinfo")
router.register(
    r"fileprocessinglogs",
    views.FileProcessingLogsviewset,
    basename="fileprocessinglogs",
)
router.register(
    r"processingstatus",
    views.ProcessingStatusviewset,
    basename="processingstatus",
)
router.register(
    r"pharmacysoftware",
    views.PharmacySoftwareviewset,
    basename="pharmacysoftware",
)


urls = [
    path("process_emails/", views.trigger_process_email, name="process_emails"),
]
urlpatterns = router.urls + urls
