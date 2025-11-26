import logging
import time
import json
from typing import Dict, Optional, List
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
        parent_report: Optional[AdvancedReport] = None,
        analysis_target_dates: Optional[List[str]] = None,
        additional_dates: Optional[List[str]] = None
    ) -> Dict:
        # 오늘 날짜 가져오기
        today = datetime.now()
        current_date = today.strftime("%Y-%m-%d")
        current_year = today.year
        current_month = today.month
        
        # 날짜 배열 구성 로직
        final_analysis_target_dates = []
        
        if parent_report:
            # 부모 보고서가 있는 경우: 부모의 날짜 상속
            if parent_report.analysis_target_dates:
                try:
                    parent_dates = json.loads(parent_report.analysis_target_dates)
                    final_analysis_target_dates = parent_dates.copy() if isinstance(parent_dates, list) else []
                except:
                    final_analysis_target_dates = []
            
            # additional_dates가 있으면 부모 날짜와 합치기 (중복 제거, 정렬)
            if additional_dates:
                final_analysis_target_dates = list(set(final_analysis_target_dates + additional_dates))
                final_analysis_target_dates.sort()
            
            # 날짜가 없으면 현재 날짜의 "YYYY-MM" 형식 사용
            if not final_analysis_target_dates:
                final_analysis_target_dates = [today.strftime("%Y-%m")]
        else:
            # 부모 보고서가 없는 경우
            if analysis_target_dates:
                final_analysis_target_dates = analysis_target_dates.copy()
            else:
                # 날짜가 없으면 현재 날짜의 "YYYY-MM" 형식 사용
                final_analysis_target_dates = [today.strftime("%Y-%m")]
        
        # 여러 날짜 분석 여부 판단
        is_multi_date_analysis = len(final_analysis_target_dates) > 1
        
        # 부모 보고서가 있으면 컨텍스트에 추가
        if parent_report:
            dates_info = ", ".join(final_analysis_target_dates) if final_analysis_target_dates else "날짜 정보 없음"
            initial_message = f"""
{organization_name}에 대한 보고서를 작성해주세요.

이전 보고서 내용:
{parent_report.final_report}

이 보고서에 대한 추가 질문:
{user_command}

분석 대상 날짜: {dates_info}
오늘 날짜: {current_date}
현재 진행 중인 공연/전시만 포함해주세요.

위 이전 보고서를 참고하여, 추가 질문 "{user_command}"에 집중해서 더 세부적인 분석을 수행하고 전문적인 보고서를 작성하세요.
""".strip()
        else:
            dates_info = ", ".join(final_analysis_target_dates) if final_analysis_target_dates else "날짜 정보 없음"
            initial_message = f"""
{organization_name}에 대한 보고서를 작성해주세요.

사용자 요청:
{user_command}

분석 대상 날짜: {dates_info}
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
                "analysis_target_dates": final_analysis_target_dates,  # 분석 대상 날짜 배열
                "is_multi_date_analysis": is_multi_date_analysis,  # 여러 날짜 분석 여부
            },
            "messages": [HumanMessage(content=initial_message)],
        }

    async def generate_report(
        self,
        organization_name: str,
        user_command: str,
        report_type: str = "user",
        parent_report: Optional[AdvancedReport] = None,
        analysis_target_dates: Optional[List[str]] = None,
        additional_dates: Optional[List[str]] = None
    ) -> Dict:
        try:
            # 시작 시간 기록
            start_time = time.time()
            logger.info(f"Starting report generation for {organization_name}")
            if parent_report:
                logger.info(f"Parent report ID: {parent_report.id}, Depth: {parent_report.depth}")
            if analysis_target_dates:
                logger.info(f"Analysis target dates: {analysis_target_dates}")
            if additional_dates:
                logger.info(f"Additional dates: {additional_dates}")
            
            graph = self._get_graph()
            initial_state = self._build_initial_state(
                organization_name, 
                user_command, 
                report_type, 
                parent_report,
                analysis_target_dates,
                additional_dates
            )
            
            # 최종 날짜 배열 가져오기 (반환값에 포함하기 위해)
            final_dates = initial_state["request_context"].get("analysis_target_dates", [])
            
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
                "analysis_target_dates": final_dates,  # 분석 대상 날짜 배열 추가
            }
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}", exc_info=True)
            raise


agent_report_service = AgentReportService()

