from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(
    r"pharmacyauditdata", views.PharmacyAuditDataviewset, basename="pharmacyauditdata"
)
router.register(r"distributors", views.Distributorsviewset, basename="distributors")
router.register(
    r"distributorauditdata",
    views.DistributorAuditDataviewset,
    basename="distributorauditdata",
)
router.register(r"filedbmapping", views.FileDBMappingviewset, basename="filedbmapping")
router.register(r"paymentmethod", views.PaymentMethodviewset, basename="paymentmethod")
router.register(r"claimstatus", views.ClaimStatusviewset, basename="claimstatus")
router.register(r"filetype", views.FileTypeviewset, basename="filetype")
router.register(r"processloghdr", views.ProcessLogHdrviewset, basename="processloghdr")
router.register(
    r"processlogdetail", views.ProcessLogDetailviewset, basename="processlogdetail"
)
router.register(r"bingroups", views.BinGroupsviewset, basename="bingroups")
router.register(r"binnumbers", views.BinNumbersviewset, basename="binnumbers")
router.register(r"cleanfileslog", views.CleanFilesLogviewset, basename="cleanfileslog")
router.register(r"errorlogs", views.Errorlogsviewset, basename="errorlog")
router.register(r"errorseverity", views.ErrorSeverityviewset, basename="errorseverity")
urls = [
    # path(
    #     "run_comparision_process/",
    #     views.run_comparision_process,
    #     name="run_comparision_process",
    # ),
]
urlpatterns = router.urls + urls
