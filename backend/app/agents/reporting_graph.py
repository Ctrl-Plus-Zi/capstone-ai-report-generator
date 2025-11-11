from typing import Dict, Optional

from langchain_openai import ChatOpenAI

from .graph_setup import SetGraph
from .graph_util import ReportingTools


# 보고서 자동화 파이프라인을 구성하는 그래프 클래스
class ReportingGraph:

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        self.research_llm = ChatOpenAI(
            model=self.config.get("research_llm_model", "gpt-5-nano"),
            temperature=self.config.get("research_llm_temperature", 0.2),
        )
        self.analysis_llm = ChatOpenAI(
            model=self.config.get("analysis_llm_model", "gpt-4o"),
            temperature=self.config.get("analysis_llm_temperature", 0.2),
        )

        self.toolkit = ReportingTools()

        self.graph_setup = SetGraph(
            self.research_llm,
            self.analysis_llm,
            self.toolkit,
        )
        self.graph = self.graph_setup.set_graph()
