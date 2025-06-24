from django.apps import apps as global_apps
from users.constants import AccessControlTypeCodes


def create_access_controls(app_config, apps=global_apps, **kwargs):
    tables = apps.get_model("core", "Tablename")
    table_attrs = apps.get_model("core", "Tableattribute")
    AccessControl = app_config.get_model("AccessControl")
    access_control_type = app_config.get_model("AccessControlType")
    RoleAccessControl = app_config.get_model("RoleAccessControl")
    Userrole = app_config.get_model("Userrole")
    access_control_type_objs = access_control_type.objects.all()
    user_role_objs = Userrole.objects.all()
    AccessType = app_config.get_model("AccessType")
    entity_control_type = access_control_type_objs.filter(
        code=AccessControlTypeCodes.Entity.value
    ).last()
    attr_control_type = access_control_type_objs.filter(
        code=AccessControlTypeCodes.Attribute.value
    ).last()
    access_type = AccessType.objects.filter(code="FULL").last()

    all_access = set(
        AccessControl.objects.values_list("access_name", "access_control_type")
    )
    access_controls = []
    role_access_controls = []

    def get_access_control_objs(access_name, access_control_type):
        access_control = AccessControl()
        access_control.access_name = access_name
        access_control.access_control_type = access_control_type
        for role in user_role_objs:
            role_access_control = RoleAccessControl()
            role_access_control.access_control = access_control
            role_access_control.access_type = access_type
            role_access_control.role = role
            role_access_controls.append(role_access_control)
        access_controls.append(access_control)

    for table in tables.objects.all():
        if (table.name, entity_control_type.id) not in all_access:
            get_access_control_objs(table.name, entity_control_type)

    for table_attr in table_attrs.objects.all():
        if (table_attr.attrib_name, attr_control_type.id) not in all_access:
            get_access_control_objs(table_attr.attrib_name, attr_control_type)

    AccessControl.objects.bulk_create(access_controls)
    RoleAccessControl.objects.bulk_create(role_access_controls)
