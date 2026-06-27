from fastapi import APIRouter, Body
from app.services.mailer.services import MailService
from typing import Annotated, Optional
from pydantic import EmailStr 
from app.core.class_router import class_router
import logging

logging.basicConfig(level = logging.DEBUG)
logger = logging.getLogger(__name__)


router = APIRouter()

@class_router(router)
class Mailer:
    def __init__(self):
        self.mail_service = MailService()
    
    @router.post(
        "/send-mail",
        summary = "Send report to student"
    )
    async def send_mail(self,
                        report_id: Annotated[str, Body(embed=True)]=None,
                        to_email: Annotated[EmailStr, Body(embed=True)]=None,
                        ):
        logger.info("Start send mail..")
        try:
            report_title = "Student Assessment Report"

            return await self.mail_service.send_report_email(report_id=report_id,to_email=to_email, subject=report_title)
        except Exception as e:
            return f"Failed to send mail: {e}"