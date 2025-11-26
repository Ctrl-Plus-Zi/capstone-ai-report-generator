from typing import Annotated, List, TypedDict
from langchain_core.messages import BaseMessage


# 보고서 자동화 에이전트들이 공유하는 상태
class ReportingAgentState(TypedDict, total=False):

    # === 요청 컨텍스트 ===
    request_context: Annotated[dict, "보고서 요청에서 전달된 메타데이터(문화시설명, 질문 등)."]
    messages: Annotated[List[BaseMessage], "LLM과 주고받은 전체 대화 메시지 기록."]

    # === Search Agent 출력 ===
    research_notes: Annotated[str, "조사 에이전트가 수집하여 정리한 주요 메모."]
    research_sources: Annotated[List[str], "조사 단계에서 확인된 참고 출처 목록."]
    research_payload: Annotated[List[dict], "조사 에이전트가 수집한 도구 결과 샘플 (도구명, 인자, 결과 개수, 샘플 데이터)."]
    latest_performance_image: Annotated[str, "가장 최근 공연/전시 이미지 URL (예술의전당 공연 정보 또는 국립현대미술관 전시 정보가 있을 때)."]
    
    # === 기존 차트 데이터 (호환용, deprecated) ===
    chart_data: Annotated[dict, "[deprecated] 기존 차트 표시용 데이터. block_drafts로 대체 예정."]
    rating_statistics: Annotated[dict, "[deprecated] 기존 구글맵 리뷰 평점 통계. block_drafts로 대체 예정."]

    # === Analyse Agent 출력 (기존, 호환용) ===
    analysis_outline: Annotated[str, "[deprecated] 보고서 구조를 잡기 위한 분석 개요. block_drafts로 대체 예정."]
    analysis_findings: Annotated[str, "[deprecated] 분석 단계에서 도출한 핵심 인사이트 요약. block_drafts로 대체 예정."]
    
    # === Analyse Agent 출력 (신규, Server-Driven UI) ===
    block_drafts: Annotated[List[dict], "분석 에이전트가 생성한 블록 초안 배열 (markdown, chart, table, image)."]

    # === Compose Agent 출력 (기존, 호환용) ===
    final_report: Annotated[str, "[deprecated] 기존 마크다운 보고서 본문. blocks로 대체 예정."]
    compose_prompt: Annotated[str, "작성 에이전트가 사용한 프롬프트 전문."]
    
    # === Compose Agent 출력 (신규, Server-Driven UI) ===
    blocks: Annotated[List[dict], "최종 보고서 블록 배열 (row 컨테이너 포함). 프론트엔드에서 직접 렌더링."]
