from typing import Dict, Optional

from langchain_openai import ChatOpenAI

from .graph_setup import SetGraph
from .graph_util import ReportingTools


# 보고서 자동화 파이프라인을 구성하는 그래프 클래스
class ReportingGraph:

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        # gpt-5-nano는 temperature 0.2를 지원하지 않으므로 기본값(1) 사용
        research_model = self.config.get("research_llm_model", "gpt-5-nano")
        if research_model == "gpt-5-nano":
            research_temperature = self.config.get("research_llm_temperature", 1.0)
        else:
            research_temperature = self.config.get("research_llm_temperature", 0.2)

        self.research_llm = ChatOpenAI(
            model=research_model,
            temperature=research_temperature,
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
