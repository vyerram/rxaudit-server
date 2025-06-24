from django.db import models
from core.models import CoreModel, CoreLookupModel


class Person(CoreModel):
    first_name = models.CharField(
        db_column="per_first_name", max_length=128, blank=True, null=True
    )
    last_name = models.CharField(
        db_column="per_last_name", max_length=128, blank=True, null=True
    )
    email = models.CharField(
        db_column="per_email", max_length=128, blank=True, null=True
    )
    cell = models.CharField(db_column="per_cell", max_length=128, blank=True, null=True)
    phone = models.CharField(
        db_column="per_phone", max_length=128, blank=True, null=True
    )

    class Meta:
        db_table = "OPT_PER_Person"


class Address(CoreModel):
    line1 = models.CharField(db_column="adr_line1", max_length=128)
    line2 = models.CharField(
        db_column="adr_line2", max_length=128, blank=True, null=True
    )
    line3 = models.CharField(
        db_column="adr_line3", max_length=128, blank=True, null=True
    )
    city = models.CharField(db_column="adr_city", max_length=128, blank=True, null=True)
    state = models.CharField(db_column="adr_state", max_length=128)
    zip = models.IntegerField(db_column="adr_zip")
    zip_plus_four = models.IntegerField(
        db_column="adr_zip_plus_four", blank=True, null=True
    )
    country = models.CharField(
        db_column="adr_country", max_length=128, blank=True, null=True
    )

    def _get_city_state_zip(self):
        return rf"{self.city}-{self.state}-{self.zip}"

    city_state_zip = property(_get_city_state_zip)

    class Meta:
        db_table = "OPT_ADR_Address"
