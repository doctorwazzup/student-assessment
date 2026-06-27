from fastapi.routing import APIRouter
from app.api.controller.mailer import router_mailer
from app.api.controller.reports import router_reports
from app.api.controller.admin import router_admin
api_router = APIRouter()

# register all routers
api_router.include_router(router_mailer, prefix="/mail", tags=["Mail"])
api_router.include_router(router_reports, prefix="/reports", tags=["Reports"])
api_router.include_router(router_admin, prefix="/admin", tags=["Admin"])


