from __future__ import annotations

import json
import textwrap
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


def create_analyse_agent(tool_llm, summary_llm, toolkit):
    """조사 결과를 해석해 인사이트로 정리하는 분석 에이전트 노드를 생성합니다."""

    def analyse_agent_node(state):
        tools = [
            toolkit.analyse_quantitative_metrics,
            toolkit.analyse_qualitative_feedback,
        ]

        request_context = state.get("request_context", {})
        research_notes = state.get("research_notes", "")
        research_sources = state.get("research_sources", [])
        messages: List = list(state.get("messages", []))

        system_text = textwrap.dedent(
            """
            당신은 보고서 작성 파이프라인의 분석 에이전트입니다. 수집된 자료를 검토하고 어떤 관점에서 분석할지 개요를 세우세요.
            필요한 경우 도구를 호출해 추가 분석을 진행합니다.

            요청 컨텍스트: {request_context}
            조사 노트: {research_notes}
            참고 출처: {research_sources}
            """
        ).strip()

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_text),
                MessagesPlaceholder(variable_name="messages"),
            ]
        ).partial(
            request_context=json.dumps(request_context, ensure_ascii=False, indent=2),
            research_notes=research_notes,
            research_sources=json.dumps(research_sources, ensure_ascii=False, indent=2),
        )

        chain = prompt | tool_llm.bind_tools(tools)
        ai_response = chain.invoke({"messages": messages})
        messages.append(ai_response)

        analysis_outline = getattr(ai_response, "content", "").strip()
        analysis_findings = state.get("analysis_findings")

        if hasattr(ai_response, "tool_calls"):
            for call in ai_response.tool_calls:
                tool_fn = next((t for t in tools if t.name == call.get("name")), None)
                if tool_fn is None:
                    continue
                tool_args = call.get("args", {})
                tool_result = tool_fn.invoke(tool_args)
                messages.append(
                    ToolMessage(
                        tool_call_id=call.get("id"),
                        content=json.dumps(tool_result) if tool_result is not None else "{}",
                    )
                )
                if isinstance(tool_result, dict):
                    notes = tool_result.get("analysis_notes")
                    if notes:
                        note_entry = f"- {notes}"
                        analysis_outline = (
                            f"{analysis_outline}\n{note_entry}".strip() if analysis_outline else note_entry
                        )

        summary_input = analysis_outline or research_notes
        summary_messages = [
            SystemMessage(content="보고서에 포함할 핵심 분석 결과를 간결하게 요약해 주세요."),
            HumanMessage(content=summary_input or "분석에 사용할 입력 자료가 제공되지 않았습니다."),
        ]
        summary_response = summary_llm.invoke(summary_messages)
        messages.append(summary_response)
        analysis_findings = summary_response.content.strip() if summary_response else (analysis_findings or "")

        if not analysis_outline:
            analysis_outline = "도구와 LLM 분석이 연결되면 여기에서 분석 개요를 정리하세요."
        if not analysis_findings:
            analysis_findings = "도구 연동 이후 분석 결과 요약이 채워질 예정입니다."

        return {
            "messages": messages,
            "analysis_outline": analysis_outline,
            "analysis_findings": analysis_findings,
        }

    return analyse_agent_node
