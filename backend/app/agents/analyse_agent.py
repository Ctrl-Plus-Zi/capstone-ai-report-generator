from __future__ import annotations

import json
import textwrap
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


# 수집된 자료를 분석하고 보고서 초안을 작성하는 분석 에이전트 노드 생성 
def create_analyse_agent(tool_llm, summary_llm, toolkit):

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
            당신은 문화시설 보고서 자동 작성을 지원하는 분석 에이전트입니다.    
            수집된 자료를 검토하고 중요한 관점을 파악하여 필요한 경우 후속 도구 호출을 계획하세요.

            요청 컨텍스트: {request_context}
            조사 메모: {research_notes}
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
            SystemMessage(content="보고서에 대한 핵심 분석 결과를 요약해주세요."),
            HumanMessage(content=summary_input or "분석 입력이 제공되지 않았습니다."),
        ]
        summary_response = summary_llm.invoke(summary_messages)
        messages.append(summary_response)
        analysis_findings = summary_response.content.strip() if summary_response else (analysis_findings or "")

        if not analysis_outline:
            analysis_outline = "도구와 LLM 분석이 완료되면 이 부분을 채워 주세요."
        if not analysis_findings:
            analysis_findings = "도구 통합이 완료되면 분석 결과가 생성됩니다."

        return {
            "messages": messages,
            "analysis_outline": analysis_outline,
            "analysis_findings": analysis_findings,
        }

    return analyse_agent_node
