"""Server-Driven Report UI API 엔드포인트

/report/v2 엔드포인트는 블록 기반 보고서를 생성합니다.
block_reports 테이블에 저장됩니다.
"""

import json
import logging
import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.block_report import BlockReport
from app.schemas.block_report import BlockReportRequest, BlockReportResponse
from app.services.block_report_service import block_report_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/report", tags=["block-report"])


@router.post("/v2", response_model=BlockReportResponse)
async def generate_block_report(
    request: BlockReportRequest,
    db: Session = Depends(get_db)
):
    """Server-Driven UI 블록 기반 보고서를 생성하고 DB에 저장합니다.
    
    프론트엔드에서 blocks 배열을 순서대로 렌더링합니다.
    """
    try:
        start_time = time.time()
        logger.info(f"[BLOCK_REPORT] 보고서 생성 시작: {request.organization_name}")
        
        # 보고서 생성
        result = await block_report_service.generate_block_report(
            organization_name=request.organization_name,
            user_command=request.user_command,
            report_type=request.report_type or "user",
            analysis_target_dates=request.analysis_target_dates,
        )
        
        # 소요 시간 계산
        generation_time = round(time.time() - start_time, 2)
        blocks = result.get("blocks", [])
        logger.info(f"[BLOCK_REPORT] 보고서 생성 완료: {generation_time}초, blocks={len(blocks)}개")
        
        # DB에 저장
        block_report = BlockReport(
            organization_name=request.organization_name,
            user_command=request.user_command,
            report_topic=request.user_command,
            report_type=request.report_type or "user",
            blocks_json=blocks,  # JSONB로 저장
            final_report=result.get("final_report"),
            research_sources_json=json.dumps(result.get("research_sources", []), ensure_ascii=False),
            analysis_target_dates_json=json.dumps(request.analysis_target_dates, ensure_ascii=False) if request.analysis_target_dates else None,
            generation_time_seconds=generation_time,
        )
        
        db.add(block_report)
        db.commit()
        db.refresh(block_report)
        
        logger.info(f"[BLOCK_REPORT] DB 저장 완료: id={block_report.id}")
        
        return BlockReportResponse(
            id=block_report.id,
            title=f"{request.organization_name} 분석 보고서",
            organization_name=block_report.organization_name,
            report_topic=block_report.report_topic,
            created_at=block_report.created_at,
            generation_time_seconds=block_report.generation_time_seconds,
            blocks=block_report.blocks_json,
            report_type=block_report.report_type,
            analysis_target_dates=request.analysis_target_dates,
            research_sources=result.get("research_sources", []),
            final_report=block_report.final_report,
        )
        
    except Exception as e:
        logger.error(f"[BLOCK_REPORT] 보고서 생성 실패: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"보고서 생성 실패: {str(e)}")


@router.get("/v2/{report_id}", response_model=BlockReportResponse)
async def get_block_report(
    report_id: int,
    db: Session = Depends(get_db)
):
    """저장된 블록 보고서를 조회합니다."""
    try:
        report = db.query(BlockReport).filter(BlockReport.id == report_id).first()
        
        if not report:
            raise HTTPException(status_code=404, detail="보고서를 찾을 수 없습니다.")
        
        # research_sources 파싱
        research_sources = []
        if report.research_sources_json:
            try:
                research_sources = json.loads(report.research_sources_json)
            except json.JSONDecodeError:
                research_sources = []
        
        # analysis_target_dates 파싱
        analysis_target_dates = None
        if report.analysis_target_dates_json:
            try:
                analysis_target_dates = json.loads(report.analysis_target_dates_json)
            except json.JSONDecodeError:
                analysis_target_dates = None
        
        return BlockReportResponse(
            id=report.id,
            title=f"{report.organization_name} 분석 보고서",
            organization_name=report.organization_name,
            report_topic=report.report_topic,
            created_at=report.created_at,
            generation_time_seconds=report.generation_time_seconds,
            blocks=report.blocks_json,
            report_type=report.report_type,
            analysis_target_dates=analysis_target_dates,
            research_sources=research_sources,
            final_report=report.final_report,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BLOCK_REPORT] 보고서 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"보고서 조회 실패: {str(e)}")


@router.get("/v2", response_model=List[BlockReportResponse])
async def list_block_reports(
    organization_name: str = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """저장된 블록 보고서 목록을 조회합니다."""
    try:
        query = db.query(BlockReport)
        
        if organization_name:
            query = query.filter(BlockReport.organization_name.ilike(f"%{organization_name}%"))
        
        reports = query.order_by(BlockReport.created_at.desc()).offset(offset).limit(limit).all()
        
        result = []
        for report in reports:
            # research_sources 파싱
            research_sources = []
            if report.research_sources_json:
                try:
                    research_sources = json.loads(report.research_sources_json)
                except json.JSONDecodeError:
                    research_sources = []
            
            # analysis_target_dates 파싱
            analysis_target_dates = None
            if report.analysis_target_dates_json:
                try:
                    analysis_target_dates = json.loads(report.analysis_target_dates_json)
                except json.JSONDecodeError:
                    analysis_target_dates = None
            
            result.append(BlockReportResponse(
                id=report.id,
                title=f"{report.organization_name} 분석 보고서",
                organization_name=report.organization_name,
                report_topic=report.report_topic,
                created_at=report.created_at,
                generation_time_seconds=report.generation_time_seconds,
                blocks=report.blocks_json,
                report_type=report.report_type,
                analysis_target_dates=analysis_target_dates,
                research_sources=research_sources,
                final_report=report.final_report,
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"[BLOCK_REPORT] 보고서 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"보고서 목록 조회 실패: {str(e)}")

