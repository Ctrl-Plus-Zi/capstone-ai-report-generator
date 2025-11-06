import logging
from typing import Dict
from langchain_core.messages import HumanMessage
import dotenv

from app.agents.reporting_graph import ReportingGraph

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
        user_command: str
    ) -> Dict:
        initial_message = f"""
{organization_name}에 대한 보고서를 작성해주세요.

사용자 요청:
{user_command}

위 요청을 바탕으로 필요한 데이터를 수집하고 분석하여 전문적인 보고서를 작성하세요.
""".strip()

        return {
            "request_context": {
                "organization_name": organization_name,
                "report_topic": user_command,
                "questions": [user_command],
            },
            "messages": [HumanMessage(content=initial_message)],
        }

    async def generate_report(
        self,
        organization_name: str,
        user_command: str
    ) -> Dict:
        try:
            logger.info(f"Starting report generation for {organization_name}")
            
            graph = self._get_graph()
            initial_state = self._build_initial_state(organization_name, user_command)
            
            result = graph.graph.invoke(initial_state)
            
            return {
                "final_report": result.get("final_report", ""),
                "research_sources": result.get("research_sources", []),
                "analysis_summary": result.get("analysis_findings", ""),
                "report_topic": user_command,
            }
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}", exc_info=True)
            raise


agent_report_service = AgentReportService()

