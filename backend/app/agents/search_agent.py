from __future__ import annotations

import json
import textwrap
from typing import List

from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


# 보고서 초안을 위한 자료를 수집하는 조사 에이전트 노드 생성 
def create_search_agent(llm, toolkit):

    def search_agent_node(state):
        tools = [
            toolkit.search_internal_documents,
            toolkit.search_external_api,
            toolkit.fetch_data_snapshot,
        ]

        request_context = state.get("request_context", {})
        messages: List = list(state.get("messages", []))

        system_text = textwrap.dedent(
            """
            당신은 문화시설 보고서 자동 작성을 지원하는 조사 에이전트입니다.
            다음 요청 정보를 검토하고 필요한 배경 자료를 어떻게 확보할지 계획을 세우세요.

            요청 컨텍스트: {request_context}
            적절하다고 판단되면 도구를 호출해 참고 자료를 축적하세요. 아직 구현되지 않은 도구라면 메모 형태로 계획을 남기면 됩니다.
            """
        ).strip()

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_text),
                MessagesPlaceholder(variable_name="messages"),
            ]
        ).partial(request_context=json.dumps(request_context, ensure_ascii=False, indent=2))

        chain = prompt | llm.bind_tools(tools)
        ai_response = chain.invoke({"messages": messages})
        messages.append(ai_response)

        research_notes = state.get("research_notes")
        research_sources = list(state.get("research_sources", []))

        if hasattr(ai_response, "tool_calls"):
            for call in ai_response.tool_calls:
                tool_name = call.get("name")
                tool_args = call.get("args", {})
                tool_fn = next((t for t in tools if t.name == tool_name), None)
                if tool_fn is None:
                    continue
                tool_result = tool_fn.invoke(tool_args)
                messages.append(
                    ToolMessage(
                        tool_call_id=call.get("id"),
                        content=json.dumps(tool_result) if tool_result is not None else "{}",
                    )
                )
                if isinstance(tool_result, dict):
                    notes = tool_result.get("notes")
                    if notes:
                        note_entry = f"- {notes}"
                        research_notes = (
                            f"{research_notes}\n{note_entry}".strip() if research_notes else note_entry
                        )
                    sources = tool_result.get("sources")
                    if sources:
                        research_sources.extend(sources)

        summary_text = getattr(ai_response, "content", "").strip()
        if summary_text:
            research_notes = summary_text if research_notes is None else research_notes

        if not research_notes:
            research_notes = "조사 단계가 초기화되었습니다. 도구 구현이 완료되면 이 부분을 채워 주세요."

        return {
            "messages": messages,
            "research_notes": research_notes,
            "research_sources": research_sources,
        }

    return search_agent_node
