from django.conf import settings
from http import HTTPStatus
import requests
import logging

from apps.pms.schemas.auth import PmsLicenseRequest, PmsLicenseResponse
from core.exceptions import AppError
from apps.pms.utils import (
    build_endpoint_url,
)


logger = logging.getLogger(__name__)

class PmsLicenseAuthService:
    def __init__(self):
        self.pms_ip = settings.PMS_IP
        self.pms_port = settings.PMS_PORT
        self.endpoint = settings.PMS_AUTH_ENDPOINT
        self.base_url = build_endpoint_url(self.pms_ip, self.pms_port, self.endpoint)
        self.api_key = settings.PMS_API_KEY

    def verify_login(self, username: str, company_id: int) -> PmsLicenseResponse:
        if not settings.PMS_AUTH_ENABLED:
            logger.info("PMS auth skipped (PMS_AUTH_ENABLED=false)")
            return PmsLicenseResponse(
                allowed=True,
                expires_at=None,
                message="PMS auth disabled",
            )

        payload = PmsLicenseRequest(username=username, company_id=company_id).dict()
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            resp = requests.post(self.base_url, json=payload, headers=headers, timeout=5)
        except requests.RequestException:
            raise AppError("PMS 서버와 연결할 수 없습니다.", HTTPStatus.SERVICE_UNAVAILABLE)
        
        if not resp.ok:
            raise AppError("PMS 인증 실패", HTTPStatus.SERVICE_UNAVAILABLE)
        
        data = resp.json()
        response = PmsLicenseResponse(**data)
        
        if not response.allowed:
            raise AppError(response.message or "라이선스 만료", HTTPStatus.FORBIDDEN)
        return response
