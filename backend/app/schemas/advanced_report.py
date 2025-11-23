from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class AdvancedReportRequest(BaseModel):
    organization_name: str = Field(..., min_length=1, max_length=255)
    user_command: str = Field(..., min_length=1)
    report_type: Optional[str] = Field(default="user", description="보고서 유형: 'user' 또는 'operator'")
    parent_report_id: Optional[int] = Field(default=None, description="상위 보고서 ID (하위 보고서 생성 시)")


class RatingStatistics(BaseModel):
    total_reviews: int
    average_rating: float
    rating_distribution: dict[str, int]  # {"5": 500, "4": 400, ...}
    rating_percentages: dict[str, float]  # {"5": 40.5, "4": 32.4, ...}


class AdvancedReportResponse(BaseModel):
    id: int
    organization_name: str
    report_topic: str
    final_report: str
    research_sources: List[str]
    analysis_summary: str
    generated_at: datetime
    generation_time_seconds: float = 0.0  # 보고서 생성 소요 시간 (초)
    chart_data: dict = {}  # 차트 데이터 (월별 연령대별 성별 비율 등)
    rating_statistics: Optional[RatingStatistics] = None  # 평점 통계 데이터
    parent_report_id: Optional[int] = None  # 상위 보고서 ID
    depth: int = 0  # 계층 깊이 (0: 원본)

    class Config:
        from_attributes = True

