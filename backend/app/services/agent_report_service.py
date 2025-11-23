import logging
import time
from typing import Dict, Optional
from datetime import datetime
from langchain_core.messages import HumanMessage
import dotenv

from app.agents.reporting_graph import ReportingGraph
from app.models.advanced_report import AdvancedReport

dotenv.load_dotenv()

logger = logging.getLogger(__name__)


class AgentReportService:
    def __init__(self):
        self.reporting_graph = None

    def _get_graph(self) -> ReportingGraph:
        if self.reporting_graph is None:
            self.reporting_graph = ReportingGraph()
        return self.reporting_graph

    def _build_initial_state(
        self, 
        organization_name: str, 
        user_command: str,
        report_type: str = "user",
        parent_report: Optional[AdvancedReport] = None
    ) -> Dict:
        # 오늘 날짜 가져오기
        today = datetime.now()
        current_date = today.strftime("%Y-%m-%d")
        current_year = today.year
        current_month = today.month
        
        # 부모 보고서가 있으면 컨텍스트에 추가
        if parent_report:
            initial_message = f"""
{organization_name}에 대한 보고서를 작성해주세요.

이전 보고서 내용:
{parent_report.final_report}

이 보고서에 대한 추가 질문:
{user_command}

오늘 날짜: {current_date}
현재 진행 중인 공연/전시만 포함해주세요.

위 이전 보고서를 참고하여, 추가 질문 "{user_command}"에 집중해서 더 세부적인 분석을 수행하고 전문적인 보고서를 작성하세요.
""".strip()
        else:
            initial_message = f"""
{organization_name}에 대한 보고서를 작성해주세요.

사용자 요청:
{user_command}

오늘 날짜: {current_date}
현재 진행 중인 공연/전시만 포함해주세요.

위 요청을 바탕으로 필요한 데이터를 수집하고 분석하여 전문적인 보고서를 작성하세요.
""".strip()

        return {
            "request_context": {
                "organization_name": organization_name,
                "report_topic": user_command,
                "questions": [user_command],
                "current_date": current_date,  # 오늘 날짜 추가
                "current_year": current_year,
                "current_month": current_month,
                "filter_active_only": True,  # 현재 진행 중인 것만 필터링 플래그
                "report_type": report_type,  # 보고서 유형: 'user' 또는 'operator'
            },
            "messages": [HumanMessage(content=initial_message)],
        }

    async def generate_report(
        self,
        organization_name: str,
        user_command: str,
        report_type: str = "user",
        parent_report: Optional[AdvancedReport] = None
    ) -> Dict:
        try:
            # 시작 시간 기록
            start_time = time.time()
            logger.info(f"Starting report generation for {organization_name}")
            if parent_report:
                logger.info(f"Parent report ID: {parent_report.id}, Depth: {parent_report.depth}")
            
            graph = self._get_graph()
            initial_state = self._build_initial_state(organization_name, user_command, report_type, parent_report)
            
            result = graph.graph.invoke(initial_state)
            
            # 종료 시간 기록 및 소요 시간 계산
            end_time = time.time()
            generation_time_seconds = round(end_time - start_time, 2)
            
            logger.info(f"Report generation completed in {generation_time_seconds} seconds")
            
            return {
                "final_report": result.get("final_report", ""),
                "research_sources": result.get("research_sources", []),
                "analysis_summary": result.get("analysis_findings", ""),
                "report_topic": user_command,
                "generation_time_seconds": generation_time_seconds,
                "chart_data": result.get("chart_data", {}),  # 차트 데이터 추가
                "rating_statistics": result.get("rating_statistics"),  # 평점 통계 데이터 추가
            }
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}", exc_info=True)
            raise


agent_report_service = AgentReportService()

