from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.llm_inference_service import llm_inference_service, LLMConfig

router = APIRouter(prefix="/llm-inference", tags=["llm-inference"])


class LLMAnalysisRequest(BaseModel):
    """LLM 분석 요청"""
    custom_instructions: Optional[str] = None
    api_key: Optional[str] = None
    model: str = "gpt-4"
    dry_run: bool = True


class LLMConfigRequest(BaseModel):
    """LLM 설정 요청"""
    api_key: Optional[str] = None
    model: str = "gpt-4"
    temperature: float = 0.3
    max_tokens: int = 1500


@router.post("/analyze")
async def run_llm_analysis(
    request: LLMAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    LLM 기반 포트폴리오 분석 및 자동 트레이딩
    레퍼런스 프로젝트의 run_automated_trading() 구현
    """
    try:
        # LLM 설정 업데이트
        if request.api_key:
            llm_trading_service.config.api_key = request.api_key
        llm_trading_service.config.model = request.model
        
        # 1. 트레이딩 프롬프트 생성
        prompt = llm_trading_service.generate_trading_prompt(
            db, 
            request.custom_instructions
        )
        
        # 2. LLM API 호출
        llm_response_raw = await llm_trading_service.call_llm_api(prompt)
        
        # 3. 응답 파싱
        llm_response = llm_trading_service.parse_llm_response(llm_response_raw)
        
        # 4. 트레이딩 결정 실행
        execution_result = await llm_trading_service.execute_trading_decisions(
            db, llm_response, request.dry_run
        )
        
        return {
            "success": True,
            "message": "LLM 분석 및 트레이딩 완료",
            "prompt_length": len(prompt),
            "llm_response": {
                "analysis": llm_response.analysis,
                "confidence": llm_response.confidence,
                "reasoning": llm_response.reasoning,
                "trade_count": len(llm_response.trades)
            },
            "execution_result": execution_result,
            "dry_run": request.dry_run
        }
        
    except Exception as e:
        logger.error(f"LLM 분석 실행 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"LLM 분석 실패: {e}")


import logging
from datetime import datetime

logger = logging.getLogger(__name__)