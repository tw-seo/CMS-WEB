from django.apps import AppConfig


class CmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cms"
    verbose_name = "CMS"

    def ready(self) -> None:
        import apps.cms.signals  # noqa: F401
        from .services.workers.service_monitor import start_service_monitor
        from .services.workers.viewer_notifier import start_viewer_notifier
        from .services.workers.viewer_realtime import start_viewer_realtime_server
        from apps.pms.services.status_reporter import start_status_reporter

        # start_status_reporter()
        # start_service_monitor()
        start_viewer_realtime_server()
        start_viewer_notifier()
