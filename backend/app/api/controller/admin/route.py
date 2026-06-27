from .schema import GoalsUpdate, SaveGoalsResponse

import os
import secrets
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.core.class_router import class_router
from app.services.admin.services import AdminService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
_basic = HTTPBasic()


def require_admin(creds: HTTPBasicCredentials = Depends(_basic)) -> str:
    ok_user = secrets.compare_digest(creds.username, ADMIN_USERNAME)
    ok_pass = secrets.compare_digest(creds.password, ADMIN_PASSWORD)
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            detail="Sai tài khoản hoặc mật khẩu admin.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return creds.username


router = APIRouter()


@class_router(router)
class Admin:
    def __init__(self):
        self.admin_service = AdminService()

    @router.get("/", response_class=HTMLResponse, summary="Admin page (HTML)")
    async def admin_page(self):
        logger.info("Admin page")
        return HTMLResponse(self.admin_service.admin_html())

    @router.get("/goals", summary="Get stage thresholds")
    async def get_goals(self, _: str = Depends(require_admin)):
        logger.info("Get goals")
        return self.admin_service.get_goals()

    @router.api_route(
        "/goals",
        methods=["PUT", "POST"],
        summary="Save stage thresholds",
    )
    async def save_goals(
        self,
        payload: GoalsUpdate,
        _: str = Depends(require_admin),
    ) -> SaveGoalsResponse:
        logger.info("Save goals")
        return self.admin_service.save_goals(payload)
