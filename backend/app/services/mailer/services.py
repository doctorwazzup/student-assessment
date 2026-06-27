import os
import smtplib
import textwrap
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import logging
from pathlib import Path


load_dotenv(override= True)

logging.basicConfig(level = logging.DEBUG)
logger = logging.getLogger(__name__)

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

DEFAULT_SUBJECT = "STUDENT ASSESSMENT REPORT"
DEFAULT_BODY = textwrap.dedent("""\
    Dear Student,

    Thank you for taking the time to complete the Student Assessment Survey.

    Your participation is greatly appreciated and provides valuable insights into your
    academic experience and personal development. Based on your responses, we have
    generated the assessment report attached for your reference.

    We encourage you to review the report carefully and use it as a guide for your
    future learning, personal growth, and career planning.

    Best regards,

    Student Assessment System""")


class MailService:
    def __init__(self,):
        self.smtp_server = SMTP_SERVER
        self.smtp_port = SMTP_PORT
        self.sender_email = SENDER_EMAIL
        self.sender_password = SENDER_PASSWORD
        self.default_subject = DEFAULT_SUBJECT
        self.default_body = DEFAULT_BODY


    async def send_report_email(
        self,
        report_id:str,
        to_email: str,
        subject: str | None = None,
        body: str | None = None,
        attachment_name: str | None = None,
    ):
        logger.info("Send report email")
        if not self.sender_email or not self.sender_password:
            raise RuntimeError(
                "Error SENDER_EMAIL / SENDER_PASSWORD."
            )
        
        pdf_path = f"./reports/student_report_{report_id}.pdf"
        print("pdf path:",pdf_path)
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Not find file PDF: {pdf_path}")

        body = textwrap.dedent("""\
            Dear Student,

            Thank you for taking the time to complete the Student Assessment Survey.

            Your participation is greatly appreciated and provides valuable insights into your academic experience and personal development. Based on your responses, we have generated the assessment report below for your reference.

            We encourage you to review the report carefully and use it as a guide for your future learning, personal growth, and career planning.

            Thank you once again for your participation, and we wish you continued success in your academic journey.

            Best regards,

            Student Assessment System""")

        msg = MIMEMultipart()
        msg["From"] = self.sender_email
        msg["To"] = to_email
        msg["Subject"] = subject or self.default_subject

        msg.attach(MIMEText(body or self.default_body, "plain"))

        with open(pdf_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        filename = "Student report.pdf" 
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, to_email, msg.as_string())
        logger.info("Send mail successfuly")
        return {"to": to_email, "subject": msg["Subject"], "attachment": filename}
