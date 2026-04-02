from ninja import Router

from .auth import auth_router

router = Router()


router.add_router("/auth", auth_router)
