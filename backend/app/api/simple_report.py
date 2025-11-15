from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.simple_report_service import simple_report_service
from app.models.report import Report
from app.schemas.report import GenerateReportRequest, GenerateReportResponse

router = APIRouter(prefix="/report", tags=["simple-report"])


@router.post("/generate", response_model=GenerateReportResponse)
async def generate_report(
    request: GenerateReportRequest,
    db: Session = Depends(get_db)
):
    """
    간단한 보고서 생성
    기관명과 질문을 받아 LLM이 생성한 답변을 반환
    """
    try:
        # 1. LLM으로 보고서 생성
        response_text = await simple_report_service.generate_report(
            organization_name=request.organization_name,
            question=request.question
        )
        
        # 2. 데이터베이스에 저장
        report = Report(
            organization_name=request.organization_name,
            question=request.question,
            response=response_text
        )
        
        db.add(report)
        db.commit()
        db.refresh(report)
        
        # 3. 응답 반환
        return GenerateReportResponse(
            organization_name=request.organization_name,
            question=request.question,
            response=response_text,
            generated_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"보고서 생성 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"보고서 생성 실패: {e}")


import logging

logger = logging.getLogger(__name__)