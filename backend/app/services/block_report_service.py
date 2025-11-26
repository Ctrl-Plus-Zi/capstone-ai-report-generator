"""Server-Driven Report UI 서비스

블록 기반 보고서 생성을 담당합니다.
기존 ReportingGraph를 사용하되, blocks 출력을 반환합니다.
"""

import logging
import time
from typing import Dict, Optional, List
from datetime import datetime
from langchain_core.messages import HumanMessage
import dotenv

from app.agents.reporting_graph import ReportingGraph

dotenv.load_dotenv()

logger = logging.getLogger(__name__)


class BlockReportService:
    """Server-Driven UI 블록 기반 보고서 서비스"""
    
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
        analysis_target_dates: Optional[List[str]] = None,
    ) -> Dict:
        """초기 상태를 구성합니다."""
        today = datetime.now()
        current_date = today.strftime("%Y-%m-%d")
        current_year = today.year
        current_month = today.month
        
        # 날짜 배열 구성
        if analysis_target_dates:
            final_analysis_target_dates = analysis_target_dates.copy()
        else:
            final_analysis_target_dates = [today.strftime("%Y-%m")]
        
        is_multi_date_analysis = len(final_analysis_target_dates) > 1
        dates_info = ", ".join(final_analysis_target_dates)
        
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
                "current_date": current_date,
                "current_year": current_year,
                "current_month": current_month,
                "filter_active_only": True,
                "report_type": report_type,
                "analysis_target_dates": final_analysis_target_dates,
                "is_multi_date_analysis": is_multi_date_analysis,
            },
            "messages": [HumanMessage(content=initial_message)],
        }

    async def generate_block_report(
        self,
        organization_name: str,
        user_command: str,
        report_type: str = "user",
        analysis_target_dates: Optional[List[str]] = None,
    ) -> Dict:
        """블록 기반 보고서를 생성합니다.
        
        Returns:
            {
                "blocks": [...],          # Server-Driven UI 블록 배열
                "final_report": "...",    # 기존 호환용 마크다운
                "research_sources": [...], # 참고 출처
            }
        """
        try:
            start_time = time.time()
            logger.info(f"[BLOCK_SERVICE] 보고서 생성 시작: {organization_name}")
            
            graph = self._get_graph()
            initial_state = self._build_initial_state(
                organization_name, 
                user_command, 
                report_type, 
                analysis_target_dates
            )
            
            # 그래프 실행
            result = graph.graph.invoke(initial_state)
            
            # 결과 추출
            blocks = result.get("blocks", [])
            final_report = result.get("final_report", "")
            research_sources = result.get("research_sources", [])
            
            # 로깅
            generation_time = round(time.time() - start_time, 2)
            logger.info(f"[BLOCK_SERVICE] 보고서 생성 완료: {generation_time}초")
            logger.info(f"[BLOCK_SERVICE] - blocks: {len(blocks)}개")
            logger.info(f"[BLOCK_SERVICE] - final_report: {len(final_report)}자")
            logger.info(f"[BLOCK_SERVICE] - research_sources: {len(research_sources)}개")
            
            return {
                "blocks": blocks,
                "final_report": final_report,
                "research_sources": research_sources,
            }
            
        except Exception as e:
            logger.error(f"[BLOCK_SERVICE] 보고서 생성 실패: {e}", exc_info=True)
            raise


# 싱글톤 인스턴스
block_report_service = BlockReportService()

