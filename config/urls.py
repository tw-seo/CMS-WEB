from core.jwt import JWTAuth
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path
from ninja import NinjaAPI

from apps.account.api import router as account_router
from apps.cms.api import router as cms_router
from apps.company.api import router as company_router
from apps.masterdata.api import router as masterdata_router
from apps.mediamtx.api import router as mediamtx_router

api = NinjaAPI(title="Solution API", auth=JWTAuth())
api.add_router("", account_router)
api.add_router("", cms_router)
api.add_router("", company_router)
api.add_router("", masterdata_router)
api.add_router("", mediamtx_router)


def root(request):
    return redirect("/api/docs")  # Redirect to API docs


urlpatterns = [
    path("", root),
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
