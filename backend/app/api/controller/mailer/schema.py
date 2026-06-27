from pydantic import BaseModel, Field, EmailStr


class SendMailRequest(BaseModel):
    report_id: str | None = Field(None, description="ID report đã export trước đó (để gửi lại).")
    to_email: EmailStr | None = Field(None, description="Người nhận. Bỏ trống = dùng email trong hồ sơ SV.")
    subject: str | None = None
    body: str | None = None

    csv_url: str | None = None
    map_json_path: str | None = None
    report_title: str = "Student Assessment Report"
    subtitle: str = "Đối chiếu năng lực với ngưỡng chuẩn theo giai đoạn"


class SendMailResponse(BaseModel):
    report_id: str
    sent: dict
    