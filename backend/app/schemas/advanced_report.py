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

    class Config:
        from_attributes = True

