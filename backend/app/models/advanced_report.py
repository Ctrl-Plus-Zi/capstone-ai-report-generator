from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AdvancedReport(Base):
    __tablename__ = "advanced_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_command: Mapped[str] = mapped_column(Text, nullable=False)
    report_topic: Mapped[str] = mapped_column(String(500), nullable=False)
    final_report: Mapped[str] = mapped_column(Text, nullable=False)
    research_sources_json: Mapped[str] = mapped_column(Text, nullable=True)
    analysis_summary: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    
    # 계층 구조 필드
    parent_report_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("advanced_reports.id"),
        nullable=True,
        index=True
    )
    depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # 보고서 유형 및 날짜 필드
    report_type: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    analysis_target_dates: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON 배열 문자열 저장
    
    # 관계 설정
    parent_report: Mapped["AdvancedReport | None"] = relationship(
        "AdvancedReport",
        remote_side=[id],
        backref="child_reports"
    )

