from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.report_generation_service import report_generation_service, LLMConfig
from app.models.organization import Organization
from app.schemas.organization import (
    OrganizationCreate, OrganizationRead, OrganizationUpdate,
    ReportRequest, ReportResponse
)

router = APIRouter(prefix="/report", tags=["report-generation"])


class ReportGenerationRequest(BaseModel):
    """보고서 생성 요청"""
    organization_name: str
    report_type: str = "comprehensive"  # comprehensive, financial, operational, market
    custom_instructions: Optional[str] = None
    format: str = "markdown"  # markdown, html, json
    api_key: Optional[str] = None
    model: str = "gpt-4"


class LLMConfigRequest(BaseModel):
    """LLM 설정 요청"""
    api_key: Optional[str] = None
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 3000


@router.post("/generate")
async def generate_report(
    request: ReportGenerationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    기관 보고서 생성
    조직명을 입력받아 해당 조직에 대한 보고서를 생성합니다.
    """
    try:
        # LLM 설정 업데이트
        if request.api_key:
            report_generation_service.config.api_key = request.api_key
        report_generation_service.config.model = request.model
        
        # 1. 조직 정보 확인 (옵션 - DB에서 조직 정보 조회)
        organization = db.query(Organization).filter(
            Organization.name == request.organization_name
        ).first()
        
        # 2. 보고서 생성 프롬프트 생성
        prompt = report_generation_service.generate_report_prompt(
            organization_name=request.organization_name,
            report_type=request.report_type,
            custom_instructions=request.custom_instructions
        )
        
        # 3. LLM API 호출
        llm_response_raw = await report_generation_service.call_llm_api(prompt)
        
        # 4. 응답 파싱
        parsed_report = report_generation_service.parse_llm_response(llm_response_raw)
        
        # 5. 보고서 포맷팅
        formatted_report = report_generation_service.format_report(
            parsed_report, request.format
        )
        
        # 6. 응답 생성
        report_response = ReportResponse(
            organization_name=parsed_report.organization_name,
            report_type=parsed_report.report_type,
            report_content=formatted_report,
            generated_at=datetime.now(),
            word_count=len(formatted_report.split()),
            confidence=parsed_report.confidence,
            format=request.format
        )
        
        return {
            "success": True,
            "message": f"{request.organization_name} 기관의 {request.report_type} 보고서가 성공적으로 생성되었습니다.",
            "report": report_response,
            "metadata": {
                "prompt_length": len(prompt),
                "sections_count": len(parsed_report.sections),
                "recommendations_count": len(parsed_report.recommendations),
                "organization_in_db": organization is not None
            }
        }
        
    except Exception as e:
        logger.error(f"보고서 생성 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"보고서 생성 실패: {e}")


@router.get("/history")
async def get_report_history(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """보고서 생성 히스토리 조회"""
    try:
        history = report_generation_service.get_report_history(limit)
        return {
            "success": True,
            "history": history,
            "total_reports": len(history)
        }
    except Exception as e:
        logger.error(f"히스토리 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"히스토리 조회 실패: {e}")


@router.post("/organizations")
def create_organization(
    payload: OrganizationCreate, 
    db: Session = Depends(get_db)
) -> OrganizationRead:
    """새 조직 등록"""
    try:
        # 중복 확인
        existing = db.query(Organization).filter(
            Organization.name == payload.name
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="이미 존재하는 조직명입니다.")
        
        organization = Organization(
            name=payload.name,
            description=payload.description,
            industry=payload.industry,
            location=payload.location,
            website=payload.website,
            established_year=payload.established_year,
            employee_count=payload.employee_count
        )
        
        db.add(organization)
        db.commit()
        db.refresh(organization)
        
        return organization
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"조직 생성 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"조직 생성 실패: {e}")


@router.get("/organizations")
def list_organizations(db: Session = Depends(get_db)) -> List[OrganizationRead]:
    """등록된 조직 목록 조회"""
    try:
        organizations = db.query(Organization).order_by(Organization.name).all()
        return organizations
    except Exception as e:
        logger.error(f"조직 목록 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"조직 목록 조회 실패: {e}")


@router.get("/organizations/{organization_id}")
def get_organization(
    organization_id: int, 
    db: Session = Depends(get_db)
) -> OrganizationRead:
    """특정 조직 정보 조회"""
    try:
        organization = db.query(Organization).filter(
            Organization.id == organization_id
        ).first()
        
        if not organization:
            raise HTTPException(status_code=404, detail="조직을 찾을 수 없습니다.")
        
        return organization
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"조직 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"조직 조회 실패: {e}")


@router.put("/organizations/{organization_id}")
def update_organization(
    organization_id: int,
    payload: OrganizationUpdate,
    db: Session = Depends(get_db)
) -> OrganizationRead:
    """조직 정보 업데이트"""
    try:
        organization = db.query(Organization).filter(
            Organization.id == organization_id
        ).first()
        
        if not organization:
            raise HTTPException(status_code=404, detail="조직을 찾을 수 없습니다.")
        
        # 업데이트할 필드만 수정
        update_data = payload.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(organization, field, value)
        
        db.commit()
        db.refresh(organization)
        
        return organization
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"조직 업데이트 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"조직 업데이트 실패: {e}")


@router.delete("/organizations/{organization_id}")
def delete_organization(
    organization_id: int,
    db: Session = Depends(get_db)
):
    """조직 삭제"""
    try:
        organization = db.query(Organization).filter(
            Organization.id == organization_id
        ).first()
        
        if not organization:
            raise HTTPException(status_code=404, detail="조직을 찾을 수 없습니다.")
        
        db.delete(organization)
        db.commit()
        
        return {"success": True, "message": "조직이 삭제되었습니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"조직 삭제 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"조직 삭제 실패: {e}")


@router.post("/config/llm")
async def update_llm_config(request: LLMConfigRequest):
    """LLM 설정 업데이트"""
    try:
        config = LLMConfig(
            api_key=request.api_key,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        report_generation_service.config = config
        
        return {
            "success": True,
            "message": "LLM 설정이 업데이트되었습니다.",
            "config": {
                "model": config.model,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
                "api_key_configured": bool(config.api_key)
            }
        }
        
    except Exception as e:
        logger.error(f"LLM 설정 업데이트 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"LLM 설정 업데이트 실패: {e}")


import logging
from datetime import datetime

logger = logging.getLogger(__name__)