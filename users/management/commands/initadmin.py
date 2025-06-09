from django.core.management.base import BaseCommand
from django.conf import settings

from users.models import User, Userrole
from users.constants import UserRoleCodes


class Command(BaseCommand):

    def handle(self, *args, **options):
        try:
            if User.objects.count() == 0:
                for key, value in settings.ADMINS.items():
                    username = key
                    email = value
                    password = "admin"
                    print("Creating account for %s (%s)" % (username, email))
                    admin_role = Userrole.objects.filter(
                        code=UserRoleCodes.SuperUser.value
                    ).last()
                    admin = User.objects.create_superuser(
                        email=email,
                        username=username,
                        password=password,
                        role=admin_role,
                    )
                    admin.is_active = True
                    admin.is_admin = True
                    admin.save(force_update=True)
                    print("Default admin account is created")
            else:
                print("Admin accounts can only be initialized if no Accounts exist")
        except Exception as e:
            print("Exceptoin while creating admin." + str(e))
