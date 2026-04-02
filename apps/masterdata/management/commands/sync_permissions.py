from django.core.management.base import BaseCommand
from apps.masterdata.models import PermissionGroup
from apps.masterdata.services import PermissionService

class Command(BaseCommand):
    help = "menu_list.json 기반으로 모든 권한 그룹 메뉴를 동기화합니다."

    def handle(self, *args, **options):
        service = PermissionService()
        for group in PermissionGroup.objects.all():
            service.sync(group_obj=group)
        self.stdout.write(self.style.SUCCESS("메뉴 권한 동기화 완료"))
