from django.apps import AppConfig


class MediamtxConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mediamtx"
    verbose_name = "MediaMTX"

    def ready(self) -> None:
        from .services.registry import start_mtx_registry
        from .services.watchdog import start_mtx_watchdog

        start_mtx_watchdog()
        start_mtx_registry()
