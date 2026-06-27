import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv(override=True)


SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

DEFAULT_SUBJECT = "STUDENT ASSESSMENT REPORT"

# Bảng màu đồng bộ với report PDF.
_NAVY = "#1B365D"
_TEAL = "#2A9D8F"
_INK = "#282C34"
_MUTED = "#6E7681"
_LIGHT_BG = "#F4F7FA"

# Các đoạn nội dung dùng chung cho cả bản text lẫn HTML.
_PARAGRAPHS = [
    "Thank you for taking the time to complete the Student Assessment Survey.",
    "Your participation is greatly appreciated and provides valuable insights into "
    "your academic experience and personal development. Based on your responses, we "
    "have generated the assessment report attached for your reference.",
    "We encourage you to review the report carefully and use it as a guide for your "
    "future learning, personal growth, and career planning.",
]


def _greeting(name: str | None) -> str:
    name = (name or "").strip()
    return f"Dear {name}," if name else "Dear Student,"


def _text_body(name: str | None) -> str:
    body = "\n\n".join(_PARAGRAPHS)
    return (
        f"{_greeting(name)}\n\n"
        f"{body}\n\n"
        "Best regards,\n"
        "Student Assessment System"
    )


def _html_body(name: str | None) -> str:
    paragraphs = "".join(
        f'<p style="margin:0 0 14px;font-size:15px;line-height:1.6;color:{_INK};">{p}</p>'
        for p in _PARAGRAPHS
    )
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{_LIGHT_BG};">
  <div style="max-width:600px;margin:0 auto;padding:24px 16px;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background:#ffffff;border:1px solid #DFE4EA;border-radius:10px;overflow:hidden;">
      <tr><td style="background:{_NAVY};padding:26px 28px;">
        <div style="color:#ffffff;font-size:20px;font-weight:bold;letter-spacing:.3px;">
          Student Assessment Report
        </div>
        <div style="color:#C9D6E5;font-size:13px;margin-top:4px;">
          Cá nhân hoá lộ trình phát triển sinh viên
        </div>
      </td></tr>
      <tr><td style="height:3px;background:{_TEAL};font-size:0;line-height:0;">&nbsp;</td></tr>
      <tr><td style="padding:28px;">
        <p style="margin:0 0 16px;font-size:16px;font-weight:bold;color:{_NAVY};">{_greeting(name)}</p>
        {paragraphs}
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin:18px 0;">
          <tr><td style="background:{_LIGHT_BG};border-left:3px solid {_TEAL};
                         padding:12px 16px;border-radius:4px;font-size:14px;color:{_MUTED};">
            📎 Your assessment report is attached as a PDF file.
          </td></tr>
        </table>
        <p style="margin:18px 0 0;font-size:15px;color:{_INK};">Best regards,</p>
        <p style="margin:2px 0 0;font-size:15px;font-weight:bold;color:{_NAVY};">Student Assessment System</p>
      </td></tr>
    </table>
    <p style="text-align:center;color:{_MUTED};font-size:12px;margin:16px 0 0;">
      This is an automated message. Please do not reply to this email.
    </p>
  </div>
</body>
</html>"""


def send_report_email(
    to_email: str,
    pdf_path: str,
    subject: str | None = None,
    body: str | None = None,
    attachment_name: str | None = None,
    student_name: str | None = None,
):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        raise RuntimeError(
            "Thiếu SENDER_EMAIL / SENDER_PASSWORD. Hãy set biến môi trường trước khi gửi mail."
        )
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Không tìm thấy file PDF: {pdf_path}")

    msg = MIMEMultipart("mixed")
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject or DEFAULT_SUBJECT

    # Phần nội dung: text + HTML (client chọn bản hỗ trợ). Nếu caller truyền
    # `body` riêng thì dùng làm bản text, HTML vẫn theo template cho đẹp.
    text_body = body or _text_body(student_name)
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text_body, "plain", "utf-8"))
    alt.attach(MIMEText(_html_body(student_name), "html", "utf-8"))
    msg.attach(alt)

    with open(pdf_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    filename = attachment_name or os.path.basename(pdf_path)
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    msg.attach(part)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

    return {"to": to_email, "subject": msg["Subject"], "attachment": filename}
