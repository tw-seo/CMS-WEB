from ninja import Router

from .mediamtx import mediamtx_router

router = Router()

router.add_router("/mediamtx", mediamtx_router)
