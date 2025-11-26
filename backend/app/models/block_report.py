"""Server-Driven Report UI를 위한 블록 기반 보고서 모델

이 모델은 blocks 배열을 JSONB 타입으로 저장합니다.
기존 AdvancedReport와는 별도 테이블로 관리됩니다.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BlockReport(Base):
    """Server-Driven UI 블록 기반 보고서 테이블"""
    __tablename__ = "block_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # 기본 정보
    organization_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_command: Mapped[str] = mapped_column(Text, nullable=False)
    report_topic: Mapped[str] = mapped_column(String(500), nullable=False)
    report_type: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    
    # Server-Driven UI 블록 배열 (JSONB로 저장)
    blocks_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    
    # 기존 호환용 마크다운 보고서 (선택)
    final_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # 메타데이터
    research_sources_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_target_dates_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 배열 문자열
    generation_time_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

