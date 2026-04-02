from ninja import Router

from .company import company_router

router = Router()

router.add_router("", company_router)
