from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class AdvancedReportRequest(BaseModel):
    organization_name: str = Field(..., min_length=1, max_length=255)
    user_command: str = Field(..., min_length=1)


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

    class Config:
        from_attributes = True

