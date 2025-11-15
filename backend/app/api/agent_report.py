import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.agent_report_service import agent_report_service
from app.models.advanced_report import AdvancedReport
from app.schemas.advanced_report import AdvancedReportRequest, AdvancedReportResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/report", tags=["advanced-report"])


@router.post("/advanced", response_model=AdvancedReportResponse)
async def generate_advanced_report(
    request: AdvancedReportRequest,
    db: Session = Depends(get_db)
):
    try:
        result = await agent_report_service.generate_report(
            organization_name=request.organization_name,
            user_command=request.user_command,
            report_type=request.report_type
        )
        
        advanced_report = AdvancedReport(
            organization_name=request.organization_name,
            user_command=request.user_command,
            report_topic=result["report_topic"],
            final_report=result["final_report"],
            research_sources_json=json.dumps(result["research_sources"], ensure_ascii=False),
            analysis_summary=result["analysis_summary"]
        )
        
        db.add(advanced_report)
        db.commit()
        db.refresh(advanced_report)
        
        # 평점 통계 데이터 변환
        rating_stats = result.get("rating_statistics")
        if rating_stats and isinstance(rating_stats, dict) and rating_stats.get("total_reviews", 0) > 0:
            from app.schemas.advanced_report import RatingStatistics
            rating_statistics = RatingStatistics(**rating_stats)
        else:
            rating_statistics = None
        
        return AdvancedReportResponse(
            id=advanced_report.id,
            organization_name=advanced_report.organization_name,
            report_topic=advanced_report.report_topic,
            final_report=advanced_report.final_report,
            research_sources=json.loads(advanced_report.research_sources_json) if advanced_report.research_sources_json else [],
            analysis_summary=advanced_report.analysis_summary or "",
            generated_at=advanced_report.created_at,
            generation_time_seconds=result.get("generation_time_seconds", 0.0),
            chart_data=result.get("chart_data", {}),  # 차트 데이터 추가
            rating_statistics=rating_statistics  # 평점 통계 데이터 추가
        )
        
    except Exception as e:
        logger.error(f"Advanced report generation failed: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

