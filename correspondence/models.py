from django.db import models

from core.models import CoreModel


class Template(CoreModel):
    template_form = models.TextField(
        db_column="tpl_template_form", blank=True, null=True
    )
    template_file = models.TextField(
        db_column="tpl_template_file", blank=True, null=True
    )

    def __str__(self):
        return f"Template {self.id}"

    class Meta:
        db_table = "CRS_TPL_Template"


class TemplateDetails(CoreModel):
    app_name = models.CharField(
        db_column="tpd_app_name", max_length=255, blank=True, null=True
    )
    table_name = models.CharField(db_column="tpd_table_name", max_length=255)
    col_name = models.CharField(db_column="tpd_col_name", max_length=255)
    template_fieldname = models.CharField(
        db_column="tpl_template_fieldname", max_length=255
    )
    template = models.ForeignKey(
        Template,
        db_column="tpd_template",
        on_delete=models.CASCADE,
        related_name="details",
    )

    class Meta:
        db_table = "CRS_TPD_TemplateDetails"

    def __str__(self):
        return f"TemplateDetails {self.id}"
