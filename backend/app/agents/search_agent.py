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
            toolkit.search_exhibition_info_api,
            toolkit.search_museum_collection_api,
            toolkit.search_internal_documents,
            toolkit.fetch_data_snapshot,
        ]

        request_context = state.get("request_context", {})
        messages: List = list(state.get("messages", []))

        system_text = textwrap.dedent(
            """
            # 역할
            당신은 문화시설(박물관, 미술관 등) 보고서 작성을 위한 데이터 수집 전문가입니다.
            
            # 목표
            주어진 요청 컨텍스트를 분석하고, 보고서 작성에 필요한 실제 데이터를 수집하세요.
            
            # 요청 정보
            {request_context}
            
            # 사용 가능한 도구
            1. search_exhibition_info_api: 문화시설의 전시 정보 검색 (TITLE, PERIOD, DESCRIPTION, URL, CHARGE 등)
            2. search_museum_collection_api: 박물관 소장품 정보 검색 (title, description, artist, issuedDate 등)
            3. search_internal_documents: 내부 문서 검색 (구현 예정)
            4. fetch_data_snapshot: 데이터 스냅샷 가져오기 (구현 예정)
            
            # 수집 전략
            1. 요청 컨텍스트의 organization_name(기관명)을 파악하세요
            2. report_topic(보고서 주제)과 questions(질문 목록)을 분석하세요
            3. 관련성이 높은 도구를 선택하여 호출하세요:
               - 전시 정보가 필요하면 search_exhibition_info_api 사용
               - 소장품 정보가 필요하면 search_museum_collection_api 사용
            4. 검색 키워드는 organization_name과 questions에서 추출하세요
            
            # 도구 호출 가이드
            - search_exhibition_info_api: keyword에 기관의 웹사이트 URL 패턴 사용 (예: "www.museum.go.kr")
            - search_museum_collection_api: keyword에 주제 관련 키워드 사용 (예: "청자", "불상", "조선시대")
            - 각 도구는 num_of_rows 파라미터로 조회할 데이터 개수 조정 가능 (기본: 50개)
            
            # 실행 지침
            1. 반드시 하나 이상의 도구를 호출하여 실제 데이터를 수집하세요
            2. 도구 호출 후 결과를 간략히 요약하세요
            3. 수집한 데이터가 보고서 주제와 어떻게 연관되는지 설명하세요
            4. 구현되지 않은 도구는 호출하지 마세요
            
            # 출력 형식
            도구를 호출한 후, 수집한 데이터에 대한 간단한 요약을 작성하세요:
            - 어떤 데이터를 수집했는지
            - 데이터의 양과 품질
            - 보고서 작성에 어떻게 활용할 수 있는지
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
