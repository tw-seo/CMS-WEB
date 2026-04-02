from ninja import Router

from .permissions import permission_router

router = Router()

router.add_router("/permissions", permission_router)
