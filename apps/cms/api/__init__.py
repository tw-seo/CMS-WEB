"""Aggregate routers for the legacy CMS domain."""

from ninja import Router

from .api import router as setting_router
from .account import account_apply_router
from .viewer_manage import viewer_manage_router
from .buzzer.api import router as buzzer_router
from .camera.api import router as camera_router
from .dl_event.api import router as dl_event_router
from .interlock.api import router as interlock_router
from .mtx import mtx_router
from .sms.api import router as sms_router
from .agent import agent_router
router = Router()

# Keep existing public paths such as /api/camera/... by mounting at the root.
router.add_router("", setting_router)
router.add_router("/viewer-manage", viewer_manage_router)
router.add_router("/account", account_apply_router)
router.add_router("/camera", camera_router)
router.add_router("/dl_event", dl_event_router)
router.add_router("/buzzer", buzzer_router)
router.add_router("/interlock", interlock_router)
router.add_router("/sms", sms_router)
router.add_router("/mtx", mtx_router)
router.add_router("/agent", agent_router)
