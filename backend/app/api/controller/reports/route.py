from .schema import ExportRequest,ExportResponse,ScoreOut

from fastapi import APIRouter, Body,HTTPException,Query
from fastapi.responses import FileResponse
from typing import Annotated
from app.core.class_router import class_router
import os
import logging
import pipeline
logging.basicConfig(level = logging.DEBUG)
logger = logging.getLogger(__name__)


router = APIRouter()

@class_router(router)
class Reports:
    def __init__(self):
        pass
    
    async def _pdf_path_for(self,report_id: str) -> str:
        path = os.path.join(pipeline.REPORTS_DIR, f"student_report_{report_id}.pdf")
        if not os.path.exists(path):
            raise HTTPException(404, f"Not find report_id={report_id}")
        return path
    
    def _result_to_export_response(self, result: pipeline.ReportResult) -> ExportResponse:
        return ExportResponse(
            report_id=result.report_id,
            profile=result.profile,
            scores=[ScoreOut(**{k: s[k] for k in ("label", "score", "threshold", "passed")})
                    for s in result.scores],
            download_url=f"/reports/{result.report_id}",
        )
    
    @router.post("/export-report")
    async def export_report(self,
        req: ExportRequest,
        download: bool = Query(False, description="true = trả thẳng file PDF; false = trả JSON metadata."),
    ):
        """Generate report PDF for student (5 last line CSV)."""
        logger.info("Generate report...")
        try:
            result = pipeline.generate_report(
                # csv_url=req.csv_url,
                # map_json_path=req.map_json_path,
                report_title=req.report_title
           
            )
        except Exception as e:
            raise HTTPException(500, f"Error generate report: {e}")

        if download:
            return FileResponse(
                result.pdf_path,
                media_type="application/pdf",
                filename=f"student_report_{result.report_id}.pdf",
                headers={"X-Report-Id": result.report_id},
            )
        return self._result_to_export_response(result)

    @router.get("/reports/{report_id}")
    async def get_report(self,report_id:str):
        """Download PDF generated."""

        path = await self._pdf_path_for(report_id)

        return FileResponse(path, media_type="application/pdf",
                            filename=f"student_report_{report_id}.pdf")

