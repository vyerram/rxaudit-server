from http import HTTPMethod
import json
from .models import Template
from .utils import (
    get_all_fillable_data,
    write_data_to_pdfdata,
    get_model_for_fillable_pdf,
)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse, HttpResponseServerError


@api_view([HTTPMethod.GET])
@permission_classes([IsAuthenticated])
def generate_fillable_form_pdf(request):
    try:
        template_id = request.GET["template_id"]
        output_location = generate_document_for_template(template_id)
        return JsonResponse(
            {
                "status": "success",
                "message": "PDF updated successfully.",
                "output_location": output_location,
            }
        )
    except Exception as e:
        return HttpResponseServerError(str(e))


def generate_document_for_template(template_id, data: json = None):
    fillable_form_temp = (
        Template.objects.prefetch_related("details").filter(id=int(template_id)).first()
    )
    template_details = fillable_form_temp.details.all()
    data = get_data_for_pdf(template_details, data)
    output_location = write_data_to_pdfdata(fillable_form_temp, data)
    return output_location


def get_data_for_pdf(template_details, fillable_data=None):
    data = {}
    for template_detail in template_details:
        single_rec = fillable_data[0]
        if template_detail.col_name in single_rec:
            if type(single_rec[template_detail.col_name]) is not bool:
                data[template_detail.template_fieldname] = str(
                    single_rec[template_detail.col_name]
                )
            else:
                data[template_detail.template_fieldname] = single_rec[
                    template_detail.col_name
                ]
    return data
