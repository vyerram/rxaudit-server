from PyPDFForm import PdfWrapper
import io
import os
from django.apps import apps
from django.conf import settings

app_models = {}


def write_data_to_pdfdata(fillable_form_temp, data):
    template_file = fillable_form_temp.template_file
    file_name = fillable_form_temp.template_file
    template_path = os.path.join(os.getcwd(), settings.PDF_TEMPLATES, template_file)
    output_location = os.path.join(
        os.getcwd(), settings.PDF_GENERATION_LOCATION, file_name
    )
    filled = PdfWrapper(template_path).fill(data)
    with open(output_location, "wb+") as output:
        output.write(filled.read())

    return output_location


def get_model_for_fillable_pdf(template_details):
    if not app_models.keys().__contains__(template_details.table_name):
        app_models[template_details.table_name] = apps.get_model(
            app_label=template_details.app_name, model_name=template_details.table_name
        )
    return app_models[template_details.table_name]


def get_all_fillable_data(fillable_obj, fillable_data):
    if fillable_data is None:
        fillable_data = fillable_obj.objects.all()
    return fillable_data
