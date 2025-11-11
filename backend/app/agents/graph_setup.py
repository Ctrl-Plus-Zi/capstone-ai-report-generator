from langgraph.graph import END, START, StateGraph

from .agent_state import ReportingAgentState
from .analyse_agent import create_analyse_agent
from .compose_agent import create_final_report_compose_agent
from .search_agent import create_search_agent


class SetGraph:

    def __init__(self, research_llm, analysis_llm, toolkit):
        self.research_llm = research_llm
        self.analysis_llm = analysis_llm
        self.toolkit = toolkit

    def set_graph(self):
        graph = StateGraph(ReportingAgentState)

        graph.add_node("Research Agent", create_search_agent(self.research_llm, self.toolkit))
        graph.add_node(
            "Analysis Agent",
            create_analyse_agent(self.analysis_llm, self.analysis_llm, self.toolkit),
        )
        graph.add_node("Compose Agent", create_final_report_compose_agent(self.analysis_llm))

        graph.add_edge(START, "Research Agent")
        graph.add_edge("Research Agent", "Analysis Agent")
        graph.add_edge("Analysis Agent", "Compose Agent")
        graph.add_edge("Compose Agent", END)

        return graph.compile()
