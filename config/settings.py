import os
from pathlib import Path
from urllib.parse import urlparse

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-$#4q15%hk%#a8$1=4#1)#6mzk$503*17x*(6f44^e1(f$k=m0="

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "ninja_jwt",
    "mptt",

    ###
    "apps.cms.apps.CmsConfig",
    "apps.account.apps.AccountConfig",
    "apps.company.apps.CompanyConfig",
    "apps.masterdata.apps.MasterdataConfig",
    "apps.mediamtx.apps.MediamtxConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "ninja.compatibility.files.fix_request_files_middleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


BASE_DIR = Path(__file__).resolve().parent.parent
DJANGO_ENV = os.getenv("DJANGO_ENV", "dev")  # dev / prod
if DJANGO_ENV == "dev":
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env.dev")  # 로컬 개발에서만
    except Exception:
        pass

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "NAME": os.getenv("POSTGRES_DB", "DjangoP"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "CONN_MAX_AGE": 6000,
        "OPTIONS": {"options": "-c client_encoding=UTF8"},
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "ko-kr"

TIME_ZONE = "Asia/Seoul"

USE_I18N = True

USE_L10N = True

USE_TZ = False

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "account.Account"

ALLOWED_HOSTS = ["*"]


# PMS communication defaults
PMS_STATUS_REPORTING_ENABLED = os.getenv("PMS_STATUS_REPORTING_ENABLED", "true").lower() == "true"
PMS_IP = os.getenv("PMS_IP", "127.0.0.1")
PMS_PORT = os.getenv("PMS_PORT", "8080")
CMS_ID = os.getenv("CMS_ID", os.getenv("PF_IP", "UnknownCMS"))
COMPANY_NAME = os.getenv("COMPANY_NAME", os.getenv("NAME", "UnknownCompany"))
PMS_INTERVAL_HOUR = os.getenv(
    "PMS_INTERVAL_HOUR",
    os.getenv("PMS_STATUS_INTERVAL_HOURS", "1"),
)

CMS_TO_PMS_CMS_START = os.getenv("CMS_TO_PMS_CMS_START", "/api/cms_start")
CMS_TO_PMS_STATUS = os.getenv("CMS_TO_PMS_STATUS", "/api/cms_status")
PMS_AUTH_ENDPOINT = os.getenv("PMS_AUTH_ENDPOINT", "/api/license/authorize")
PMS_API_KEY = os.getenv("PMS_API_KEY", "")
PMS_AUTH_ENABLED = os.getenv("PMS_AUTH_ENABLED", "true").lower() == "true"

# Viewer and DL health check defaults
VIEWER_IP = os.getenv("VIEWER_IP", "127.0.0.1")
VIEWER_PORT = os.getenv("VIEWER_PORT", "8901")
VIEWER_HEALTH_PATH = os.getenv("VIEWER_HEALTH_PATH", "/API/is_running")
VIEWER_HEALTH_METHOD = os.getenv("VIEWER_HEALTH_METHOD", "POST").upper()
VIEWER_CMS_UPDATE_PATH = os.getenv("VIEWER_CMS_UPDATE_PATH", "/api/gui_main/mtx_info_update")
VIEWER_ALL_INFO_UPDATE_PATH = os.getenv(
    "VIEWER_ALL_INFO_UPDATE_PATH", "/api/gui_main/all_info_update"
)
VIEWER_EVT_OCCUR_PATH = os.getenv("VIEWER_EVT_OCCUR_PATH", "/api/gui_main/evt_occur")
VIEWER_ACCOUNT_INFO_CHANGE_PATH = os.getenv(
    "VIEWER_ACCOUNT_INFO_CHANGE_PATH", "/api/lite_viewer/account_info_change/"
)
VIEWER_NOTIFY_TARGETS = os.getenv("VIEWER_NOTIFY_TARGETS", "")
LITE_VIEWER_NOTIFY_TARGETS = os.getenv("LITE_VIEWER_NOTIFY_TARGETS", "")
VIEWER_NOTIFY_AUTO_DISCOVERY_ENABLED = (
    os.getenv("VIEWER_NOTIFY_AUTO_DISCOVERY_ENABLED", "true").lower() == "true"
)
VIEWER_NOTIFY_DISCOVERY_LOOKBACK_MINUTES = int(
    os.getenv("VIEWER_NOTIFY_DISCOVERY_LOOKBACK_MINUTES", "1440")
)
VIEWER_ASSIGNMENT_PUSH_ENABLED = (
    os.getenv("VIEWER_ASSIGNMENT_PUSH_ENABLED", "false").lower() == "true"
)
VIEWER_REALTIME_ENABLED = os.getenv("VIEWER_REALTIME_ENABLED", "true").lower() == "true"
VIEWER_REALTIME_HOST = os.getenv("VIEWER_REALTIME_HOST", "0.0.0.0")
VIEWER_REALTIME_PORT = int(os.getenv("VIEWER_REALTIME_PORT", "10516"))
VIEWER_REALTIME_PATH = os.getenv("VIEWER_REALTIME_PATH", "/ws/viewer")
VIEWER_REALTIME_PING_INTERVAL_SECONDS = int(
    os.getenv("VIEWER_REALTIME_PING_INTERVAL_SECONDS", "20")
)
VIEWER_REALTIME_PING_TIMEOUT_SECONDS = int(
    os.getenv("VIEWER_REALTIME_PING_TIMEOUT_SECONDS", "20")
)
VIEWER_REALTIME_REGISTER_TIMEOUT_SECONDS = int(
    os.getenv("VIEWER_REALTIME_REGISTER_TIMEOUT_SECONDS", "10")
)
VIEWER_REALTIME_SEND_TIMEOUT_SECONDS = int(
    os.getenv("VIEWER_REALTIME_SEND_TIMEOUT_SECONDS", "5")
)
VIEWER_CMS_UPDATE_ENABLED = os.getenv("VIEWER_CMS_UPDATE_ENABLED", "true").lower() == "true"
VIEWER_CMS_UPDATE_TIMEOUT_SECONDS = float(
    os.getenv("VIEWER_CMS_UPDATE_TIMEOUT_SECONDS", "5")
)
VIEWER_CMS_UPDATE_INITIAL_DELAY_SECONDS = int(
    os.getenv("VIEWER_CMS_UPDATE_INITIAL_DELAY_SECONDS", "3")
)
DL_IP = os.getenv("DL_IP", "127.0.0.1")
DL_PORT = os.getenv("DL_PORT", "8902")
DL_HEALTH_PATH = os.getenv("DL_HEALTH_PATH", "/API/is_running")
DL_HEALTH_METHOD = os.getenv("DL_HEALTH_METHOD", "POST").upper()
DL_IS_RUNNING_TIMEOUT_SECONDS = float(
    os.getenv("DL_IS_RUNNING_TIMEOUT_SECONDS", "3")
)
DL_ADD_EVENT_PATH = os.getenv("DL_ADD_EVENT_PATH", "/api/add_new_event")
DL_ADD_EVENT_TIMEOUT_SECONDS = float(os.getenv("DL_ADD_EVENT_TIMEOUT_SECONDS", "5"))
DL_ADD_ALL_EVENT_PATH = os.getenv("DL_ADD_ALL_EVENT_PATH", "/api/add_all_event")
DL_ADD_ALL_EVENT_TIMEOUT_SECONDS = float(os.getenv("DL_ADD_ALL_EVENT_TIMEOUT_SECONDS", "5"))
DL_MODIFY_EVENT_PATH = os.getenv("DL_MODIFY_EVENT_PATH", "/api/modify_one_event")
DL_MODIFY_EVENT_TIMEOUT_SECONDS = float(os.getenv("DL_MODIFY_EVENT_TIMEOUT_SECONDS", "5"))
DL_DELETE_EVENT_PATH = os.getenv("DL_DELETE_EVENT_PATH", "/api/delete_one_event")
DL_DELETE_EVENT_TIMEOUT_SECONDS = float(os.getenv("DL_DELETE_EVENT_TIMEOUT_SECONDS", "5"))
DL_DELETE_ALL_EVENT_PATH = os.getenv("DL_DELETE_ALL_EVENT_PATH", "/api/delete_all_event")
DL_DELETE_ALL_EVENT_TIMEOUT_SECONDS = float(
    os.getenv("DL_DELETE_ALL_EVENT_TIMEOUT_SECONDS", "5")
)
SERVICE_MONITOR_ENABLED = os.getenv("SERVICE_MONITOR_ENABLED", "true").lower() == "true"
SERVICE_MONITOR_INTERVAL_SECONDS = int(os.getenv("SERVICE_MONITOR_INTERVAL_SECONDS", "60"))


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() == "true"


def _build_mtx_api_base() -> str:
    base = os.getenv("MTX_API_BASE", "http://mediamtx:9997")
    parsed = urlparse(base)
    scheme = parsed.scheme or "http"
    host = os.getenv("MTX_API_HOST") or parsed.hostname or "mediamtx"
    port = os.getenv("MTX_API_PORT") or (str(parsed.port) if parsed.port else "9997")
    path = parsed.path or ""
    return f"{scheme}://{host}:{port}{path}".rstrip("/")


# MediaMTX settings (documented for .env / .env.prod)
MEDIAMTX = {
    "PUBLIC_HOST": os.getenv("PUBLIC_HOST", "127.0.0.1"),
    "API_BASE": _build_mtx_api_base(),
    "DEFAULT_ONDEMAND": _env_bool("DEFAULT_ONDEMAND", "false"),
    "TOKEN_AUTH_ENABLED": _env_bool("TOKEN_AUTH_ENABLED", "true"),
    "JWT_SECRET": os.getenv("JWT_SECRET", "supersecret_change_me"),
    "TOKEN_TTL_SEC": int(
        os.getenv("MTX_TOKEN_TTL_SEC", os.getenv("TOKEN_TTL_SEC", "300"))
    ),
    "MTX_RTSP_PORT": os.getenv("MTX_RTSP_PORT", "10314"),
    "HLS_PORT": os.getenv("MTX_HLS_PORT", "8888"),
    "WEBRTC_PORT": os.getenv("MTX_WEBRTC_PORT", "8889"),
    "SOURCE_PROTOCOL": os.getenv("MTX_SOURCE_PROTOCOL", "tcp"),
    "WATCH_DOG_ENABLED": _env_bool("MTX_WATCH_DOG", "false"),
    "WATCH_DOG_INTERVAL_SECONDS": int(os.getenv("MTX_WATCH_DOG_INTERVAL_SECONDS", "30")),
    "WATCH_DOG_TIMEOUT_SECONDS": float(os.getenv("MTX_WATCH_DOG_TIMEOUT_SECONDS", "5")),
    "WATCH_DOG_HEALTH_PATH": os.getenv("MTX_WATCH_DOG_HEALTH_PATH", "/v3/config/paths/list"),
    "REGISTRY_ENABLED": _env_bool("MTX_REGISTRY_ENABLED", "true"),
    "REGISTRY_INITIAL_DELAY_SECONDS": int(
        os.getenv("MTX_REGISTRY_INITIAL_DELAY_SECONDS", "10")
    ),
    "REGISTRY_INTERVAL_SECONDS": int(os.getenv("MTX_REGISTRY_INTERVAL_SECONDS", "60")),
    "REGISTRY_HEALTH_PATH": os.getenv("MTX_REGISTRY_HEALTH_PATH", "/v3/config/paths/list"),
    "REGISTRY_TIMEOUT_SECONDS": float(os.getenv("MTX_REGISTRY_TIMEOUT_SECONDS", "5")),
}
