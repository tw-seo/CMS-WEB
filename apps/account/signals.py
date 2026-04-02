from django.contrib.auth.hashers import make_password
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from apps.account.models import Account


@receiver(post_migrate, dispatch_uid="create_default_admin_user_once")
def create_default_admin_user(sender, **kwargs):
    admin_username = "administrator"
    admin_password = "7790"

    admin = Account.objects.filter(username=admin_username).first()
    if admin:
        admin.username = admin_username
        admin.password = make_password(admin_password)
        admin.is_staff = True
        admin.is_superuser = True
        admin.is_active = True
        admin.save(update_fields=[
            "username", "password", "is_staff", "is_superuser", "is_active"
        ])
        Account.objects.exclude(username=admin_username).update(is_superuser=False)
        print("Default admin user updated.")
        return


    Account.objects.create(
        username=admin_username,
        password=make_password(admin_password),
        is_staff=True,
        is_superuser=True,
        is_active=True,
    )
    Account.objects.exclude(username=admin_username).update(is_superuser=False)
    print("Default admin user created.")
