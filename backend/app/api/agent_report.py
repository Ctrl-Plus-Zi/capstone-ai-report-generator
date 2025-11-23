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
        # 부모 보고서 조회 및 depth 계산
        parent_report = None
        depth = 0
        if request.parent_report_id:
            parent_report = db.query(AdvancedReport).filter(
                AdvancedReport.id == request.parent_report_id
            ).first()
            if not parent_report:
                raise HTTPException(status_code=404, detail=f"Parent report with id {request.parent_report_id} not found")
            depth = parent_report.depth + 1
        
        result = await agent_report_service.generate_report(
            organization_name=request.organization_name,
            user_command=request.user_command,
            report_type=request.report_type,
            parent_report=parent_report
        )
        
        advanced_report = AdvancedReport(
            organization_name=request.organization_name,
            user_command=request.user_command,
            report_topic=result["report_topic"],
            final_report=result["final_report"],
            research_sources_json=json.dumps(result["research_sources"], ensure_ascii=False),
            analysis_summary=result["analysis_summary"],
            parent_report_id=request.parent_report_id,
            depth=depth
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
            rating_statistics=rating_statistics,  # 평점 통계 데이터 추가
            parent_report_id=advanced_report.parent_report_id,
            depth=advanced_report.depth
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Advanced report generation failed: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/{report_id}/children", response_model=list[AdvancedReportResponse])
async def get_child_reports(
    report_id: int,
    db: Session = Depends(get_db)
):
    """특정 보고서의 하위 보고서 목록을 조회합니다."""
    try:
        # 부모 보고서 존재 확인
        parent_report = db.query(AdvancedReport).filter(AdvancedReport.id == report_id).first()
        if not parent_report:
            raise HTTPException(status_code=404, detail=f"Report with id {report_id} not found")
        
        # 하위 보고서 조회
        child_reports = db.query(AdvancedReport).filter(
            AdvancedReport.parent_report_id == report_id
        ).order_by(AdvancedReport.created_at.asc()).all()
        
        result = []
        for report in child_reports:
            rating_stats = None
            if report.research_sources_json:
                try:
                    # 평점 통계는 하위 보고서에서는 선택적으로 처리
                    pass
                except:
                    pass
            
            result.append(AdvancedReportResponse(
                id=report.id,
                organization_name=report.organization_name,
                report_topic=report.report_topic,
                final_report=report.final_report,
                research_sources=json.loads(report.research_sources_json) if report.research_sources_json else [],
                analysis_summary=report.analysis_summary or "",
                generated_at=report.created_at,
                generation_time_seconds=0.0,  # 하위 보고서 조회 시에는 시간 정보 없음
                chart_data={},  # 필요시 추가
                rating_statistics=rating_stats,
                parent_report_id=report.parent_report_id,
                depth=report.depth
            ))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get child reports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get child reports: {str(e)}")

