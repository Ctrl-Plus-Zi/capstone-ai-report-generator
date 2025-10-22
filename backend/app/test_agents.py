from __future__ import annotations
from pprint import pprint
from langchain_core.messages import HumanMessage
from agents.reporting_graph import ReportingGraph
import dotenv

dotenv.load_dotenv()

def build_sample_state() -> dict:
    return {
        "request_context": {
            "organization_name": "국립중앙박물관",
            "report_topic": "2030 세대의 관람객 유입을 위한 이벤트 기획",
            "questions": [
                "2030 세대의 관람객 유입을 위한 이벤트 기획에 대해 분석해주세요.",
                "2030 세대의 관람 문화에 대해 조사해주세요.",
            ],
        },
        # Start the conversation with a single message to seed the context.
        "messages": [
            HumanMessage(content="이 요청은 자동 보고서 파이프라인 검증을 위한 더미 입력입니다.")
        ],
    }


def run_demo() -> dict:
    graph = ReportingGraph().graph
    initial_state = build_sample_state()
    return graph.invoke(initial_state)


if __name__ == "__main__":
    result_state = run_demo()
    pprint(result_state)
