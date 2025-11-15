from datetime import datetime
from pydantic import BaseModel


class ReportRequest(BaseModel):
    organization_name: str
    question: str


class ReportResponse(BaseModel):
    id: int
    organization_name: str
    question: str
    response: str
    created_at: datetime

    class Config:
        from_attributes = True


class GenerateReportRequest(BaseModel):
    organization_name: str
    question: str = "이 기관에 대해 종합적으로 분석해주세요."


class GenerateReportResponse(BaseModel):
    organization_name: str
    question: str
    response: str
    generated_at: datetime