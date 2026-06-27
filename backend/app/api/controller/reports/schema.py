from pydantic import BaseModel, Field

class ScoreOut(BaseModel):
    label: str
    score: float
    threshold: str
    passed: bool

class ExportRequest(BaseModel):
    # csv_url: str | None = Field(None, description="URL CSV khảo sát. Bỏ trống = dùng mặc định.")
    # map_json_path: str | None = Field(None, description="Đường dẫn map.json. Bỏ trống = dùng mặc định.")
    report_title: str = "Student Assessment Report"

class ExportResponse(BaseModel):
    report_id: str
    profile: dict
    scores: list[ScoreOut]
    download_url: str
