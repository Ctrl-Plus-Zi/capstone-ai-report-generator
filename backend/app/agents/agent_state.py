from typing import Annotated, List, TypedDict
from langchain_core.messages import BaseMessage


# 보고서 자동화 에이전트들이 공유하는 상태
class ReportingAgentState(TypedDict, total=False):

    request_context: Annotated[dict, "보고서 요청에서 전달된 메타데이터(문화시설명, 질문 등)."]
    messages: Annotated[List[BaseMessage], "LLM과 주고받은 전체 대화 메시지 기록."]

    research_notes: Annotated[str, "조사 에이전트가 수집하여 정리한 주요 메모."]
    research_sources: Annotated[List[str], "조사 단계에서 확인된 참고 출처 목록."]

    analysis_outline: Annotated[str, "보고서 구조를 잡기 위한 분석 개요."]
    analysis_findings: Annotated[str, "분석 단계에서 도출한 핵심 인사이트 요약."]

    final_report: Annotated[str, "최종적으로 작성된 보고서 본문."]
    compose_prompt: Annotated[str, "작성 에이전트가 사용한 프롬프트 전문."]
