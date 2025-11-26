"""Server-Driven Report UI를 위한 블록 기반 보고서 스키마

이 모듈은 /report/v2 엔드포인트에서 사용하는 요청/응답 스키마를 정의합니다.
기존 /report/advanced 와는 별도로 운영됩니다.
"""

from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# =============================================================================
# 요청 스키마
# =============================================================================

class BlockReportRequest(BaseModel):
    """Server-Driven UI 보고서 생성 요청"""
    organization_name: str = Field(..., min_length=1, max_length=255, description="분석 대상 기관명")
    user_command: str = Field(..., min_length=1, description="사용자 요청/질문")
    report_type: Optional[str] = Field(default="user", description="보고서 유형: 'user' 또는 'operator'")
    analysis_target_dates: Optional[List[str]] = Field(default=None, description="분석 대상 날짜 배열 (YYYY-MM 형식)")


# =============================================================================
# 응답 스키마 - 블록 타입들
# =============================================================================

class ChartData(BaseModel):
    """차트 데이터"""
    labels: List[str] = Field(..., description="데이터 라벨 배열")
    values: List[float] = Field(..., description="데이터 값 배열")


class MarkdownBlock(BaseModel):
    """마크다운 텍스트 블록"""
    type: Literal["markdown"] = "markdown"
    content: str = Field(..., description="마크다운 형식의 텍스트")


class ChartBlock(BaseModel):
    """Chart.js 차트 블록"""
    type: Literal["chart"] = "chart"
    chartType: str = Field(..., description="차트 유형: doughnut, bar, line, pie, radar, polarArea")
    title: str = Field(..., description="차트 제목")
    data: ChartData = Field(..., description="차트 데이터")
    description: Optional[str] = Field("", description="차트 설명")


class ImageBlock(BaseModel):
    """이미지 블록"""
    type: Literal["image"] = "image"
    url: str = Field(..., description="이미지 URL")
    alt: str = Field(..., description="대체 텍스트")
    caption: Optional[str] = Field("", description="이미지 캡션")


class TableBlock(BaseModel):
    """테이블 블록"""
    type: Literal["table"] = "table"
    title: str = Field(..., description="표 제목")
    headers: List[str] = Field(..., description="열 헤더 배열")
    rows: List[List[str]] = Field(..., description="행 데이터 2차원 배열")
    description: Optional[str] = Field("", description="표 설명")


class RowBlock(BaseModel):
    """가로 배치 컨테이너 블록"""
    type: Literal["row"] = "row"
    gap: Optional[str] = Field("16px", description="자식 요소 간 간격")
    children: List[dict] = Field(..., description="자식 블록 배열")


# =============================================================================
# 응답 스키마
# =============================================================================

class BlockReportResponse(BaseModel):
    """Server-Driven UI 보고서 응답
    
    이 응답은 DB(block_reports 테이블)에 저장됩니다.
    프론트엔드에서 blocks 배열을 순서대로 렌더링합니다.
    """
    id: int = Field(..., description="보고서 DB ID")
    title: str = Field(..., description="보고서 제목")
    organization_name: str = Field(..., description="분석 대상 기관명")
    report_topic: str = Field(..., description="보고서 주제")
    created_at: datetime = Field(..., description="생성 시각")
    generation_time_seconds: float = Field(0.0, description="생성 소요 시간 (초)")
    
    # Server-Driven UI 블록 배열
    blocks: List[dict] = Field(..., description="보고서 블록 배열")
    
    # 메타데이터
    report_type: Optional[str] = Field(None, description="보고서 유형")
    analysis_target_dates: Optional[List[str]] = Field(None, description="분석 대상 날짜")
    research_sources: List[str] = Field(default_factory=list, description="참고 출처 목록")
    
    # 기존 호환용 (선택적)
    final_report: Optional[str] = Field(None, description="기존 마크다운 보고서 (호환용)")
    
    class Config:
        from_attributes = True

