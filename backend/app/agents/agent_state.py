from typing import Annotated, List, TypedDict
from langchain_core.messages import BaseMessage


# 보고서 자동화 에이전트들이 공유하는 상태
class ReportingAgentState(TypedDict, total=False):

    # === 요청 컨텍스트 ===
    request_context: Annotated[dict, "보고서 요청에서 전달된 메타데이터(문화시설명, 질문 등)."]
    messages: Annotated[List[BaseMessage], "LLM과 주고받은 전체 대화 메시지 기록."]

    # === Search Agent 출력 ===
    research_payload: Annotated[List[dict], "조사 에이전트가 수집한 도구 결과 (도구명, 결과 개수, 샘플 데이터, block_config)."]
    latest_performance_image: Annotated[str, "가장 최근 공연/전시 이미지 URL."]
    
    # === Analyse Agent 출력 ===
    block_drafts: Annotated[List[dict], "분석 에이전트가 생성한 블록 초안 배열 (markdown, chart, table, image)."]

    # === Compose Agent 출력 ===
    final_report: Annotated[str, "마크다운 보고서 본문 (호환용)."]
    blocks: Annotated[List[dict], "최종 보고서 블록 배열 (row 컨테이너 포함). 프론트엔드에서 직접 렌더링."]
    layout_reasoning: Annotated[str, "LLM이 레이아웃을 결정한 이유 (디버깅용)."]
