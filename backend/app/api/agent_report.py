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
        parent_analysis_target_dates = None
        parent_report_type = None
        
        if request.parent_report_id:
            parent_report = db.query(AdvancedReport).filter(
                AdvancedReport.id == request.parent_report_id
            ).first()
            if not parent_report:
                raise HTTPException(status_code=404, detail=f"Parent report with id {request.parent_report_id} not found")
            depth = parent_report.depth + 1
            # 부모 보고서의 날짜 정보 가져오기
            if parent_report.analysis_target_dates:
                try:
                    parent_analysis_target_dates = json.loads(parent_report.analysis_target_dates)
                except:
                    parent_analysis_target_dates = None
            parent_report_type = parent_report.report_type
        
        # 날짜 배열 구성: 부모 날짜가 있으면 사용, 없으면 요청에서 받은 날짜 사용
        final_analysis_target_dates = parent_analysis_target_dates if parent_analysis_target_dates else request.analysis_target_dates
        # 부모 날짜와 추가 날짜 합치기
        if parent_analysis_target_dates and request.additional_dates:
            combined_dates = list(set(parent_analysis_target_dates + request.additional_dates))
            combined_dates.sort()
            final_analysis_target_dates = combined_dates
        elif request.additional_dates:
            final_analysis_target_dates = request.additional_dates
        
        # report_type 결정: 부모가 있으면 부모 타입 사용, 없으면 요청에서 받은 타입 사용
        final_report_type = parent_report_type if parent_report_type else (request.report_type or "user")
        
        result = await agent_report_service.generate_report(
            organization_name=request.organization_name,
            user_command=request.user_command,
            report_type=final_report_type,
            parent_report=parent_report,
            analysis_target_dates=final_analysis_target_dates,
            additional_dates=request.additional_dates
        )
        
        # analysis_target_dates를 JSON 문자열로 변환하여 저장
        analysis_target_dates_json = None
        if result.get("analysis_target_dates"):
            analysis_target_dates_json = json.dumps(result["analysis_target_dates"], ensure_ascii=False)
        
        advanced_report = AdvancedReport(
            organization_name=request.organization_name,
            user_command=request.user_command,
            report_topic=result["report_topic"],
            final_report=result["final_report"],
            research_sources_json=json.dumps(result["research_sources"], ensure_ascii=False),
            analysis_summary=result["analysis_summary"],
            parent_report_id=request.parent_report_id,
            depth=depth,
            report_type=final_report_type,
            analysis_target_dates=analysis_target_dates_json
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
        
        # analysis_target_dates를 JSON에서 파싱
        analysis_target_dates_list = None
        if advanced_report.analysis_target_dates:
            try:
                analysis_target_dates_list = json.loads(advanced_report.analysis_target_dates)
            except:
                analysis_target_dates_list = None
        
        # chart_data 확인 및 로깅
        chart_data = result.get("chart_data", {})
        if chart_data:
            logger.info(f"API 응답에 포함될 chart_data: keys={list(chart_data.keys())}")
            if "age_gender_ratio" in chart_data:
                logger.info(f"  - age_gender_ratio 개수: {len(chart_data['age_gender_ratio'])}")
        else:
            logger.warning("API 응답에 chart_data가 없습니다!")
        
        return AdvancedReportResponse(
            id=advanced_report.id,
            organization_name=advanced_report.organization_name,
            report_topic=advanced_report.report_topic,
            final_report=advanced_report.final_report,
            research_sources=json.loads(advanced_report.research_sources_json) if advanced_report.research_sources_json else [],
            analysis_summary=advanced_report.analysis_summary or "",
            generated_at=advanced_report.created_at,
            generation_time_seconds=result.get("generation_time_seconds", 0.0),
            chart_data=chart_data,  # 차트 데이터 추가
            rating_statistics=rating_statistics,  # 평점 통계 데이터 추가
            parent_report_id=advanced_report.parent_report_id,
            depth=advanced_report.depth,
            report_type=advanced_report.report_type,
            analysis_target_dates=analysis_target_dates_list,
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
            
            # analysis_target_dates를 JSON에서 파싱
            analysis_target_dates_list = None
            if report.analysis_target_dates:
                try:
                    analysis_target_dates_list = json.loads(report.analysis_target_dates)
                except:
                    analysis_target_dates_list = None
            
            # 하위 보고서는 chart_data를 DB에 저장하지 않으므로 빈 객체 반환
            # (차트 데이터는 부모 보고서 생성 시에만 수집됨)
            result.append(AdvancedReportResponse(
                id=report.id,
                organization_name=report.organization_name,
                report_topic=report.report_topic,
                final_report=report.final_report,
                research_sources=json.loads(report.research_sources_json) if report.research_sources_json else [],
                analysis_summary=report.analysis_summary or "",
                generated_at=report.created_at,
                generation_time_seconds=0.0,  # 하위 보고서 조회 시에는 시간 정보 없음
                chart_data={},  # 하위 보고서는 차트 데이터를 별도로 저장하지 않음
                rating_statistics=rating_stats,
                parent_report_id=report.parent_report_id,
                depth=report.depth,
                report_type=report.report_type,
                analysis_target_dates=analysis_target_dates_list
            ))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get child reports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get child reports: {str(e)}")

