from __future__ import annotations

import json
import textwrap
from typing import List


def create_final_report_compose_agent(llm):
    """최종 보고서를 작성하는 작문 에이전트 노드를 생성합니다."""

    def compose_report_node(state):
        request_context = state.get("request_context", {})
        analysis_outline = state.get("analysis_outline", "")
        analysis_findings = state.get("analysis_findings", "")
        research_notes = state.get("research_notes", "")
        messages: List = list(state.get("messages", []))

        prompt = textwrap.dedent(
            """
            당신은 최종 비즈니스 보고서를 작성하는 작가입니다. 아래 정보를 참고해 Markdown 형식의 문서를 작성하세요.
            각 주요 섹션(요약, 핵심 인사이트, 권장 사항, 후속 조치 등)은 명확히 구분해 주세요.

            요청 컨텍스트:
            {request_context}

            분석 개요:
            {analysis_outline}

            분석 결과:
            {analysis_findings}

            추가 조사 노트:
            {research_notes}
            """
        ).format(
            request_context=json.dumps(request_context, ensure_ascii=False, indent=2),
            analysis_outline=analysis_outline,
            analysis_findings=analysis_findings,
            research_notes=research_notes,
        ).strip()

        response = llm.invoke(prompt)
        messages.append(response)
        final_report = response.content.strip() if response else "보고서 작성은 도구 연동 이후 진행됩니다."

        return {
            "messages": messages,
            "final_report": final_report,
            "compose_prompt": prompt,
        }

    return compose_report_node
