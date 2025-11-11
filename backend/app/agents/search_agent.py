from __future__ import annotations
import re
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
            toolkit.search_weather_daily_api,
            toolkit.search_performance_info_api, 
            toolkit.search_internal_documents,
            toolkit.fetch_data_snapshot,
        ]

        def _extract_year_month(text: str):
            m = re.search(r'(\d{4})\s*[-./]?\s*(?:년)?\s*(1[0-2]|0?[1-9])\s*(?:월)?', text)
            if m:
                return int(m.group(1)), int(m.group(2))
            return None, None

        request_context = state.get("request_context", {})
        messages: List = list(state.get("messages", []))

        user_text = " ".join([m.content for m in messages if getattr(m, "content", None)])
        year, month = _extract_year_month(user_text)
        weather_params = dict(request_context.get("weather_params") or {})
        if year and month:
            weather_params.update({"year": year, "month": month})
        state["weather_params"] = weather_params  # 이후 가드에서 사용

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
            3. search_weather_daily_api: 기상청 ASOS 일자료(일별)를 월 단위로 조회 (tm, sumRn, maxTa, minTa 등)
            4. search_internal_documents: 내부 문서 검색 (구현 예정)
            5. fetch_data_snapshot: 데이터 스냅샷 가져오기 (구현 예정)
            6. search_performance_info_api: 예술의 전당 공연 정보 검색

            # 수집 전략
            1. 요청 컨텍스트의 organization_name(기관명)을 파악하세요
            2. report_topic(보고서 주제)과 questions(질문 목록)을 분석하세요
            3. 관련성이 높은 도구를 선택하여 호출하세요:
               - 전시 정보가 필요하면 search_exhibition_info_api 사용
               - 소장품 정보가 필요하면 search_museum_collection_api 사용
               - 공연 정보가 필요하면 search_performance_info_api 사용
               - 특정 월별 날씨/강수/기온 경향이 필요하면 search_weather_daily_api 사용
            4. 검색 키워드는 organization_name과 questions에서 추출하세요
            5. 불필요한 대량 호출/중복 호출 금지
            
            # 도구 호출 가이드
            - search_exhibition_info_api: keyword에 기관의 웹사이트 URL 패턴 사용 (예: "www.museum.go.kr")
            - search_museum_collection_api: keyword에 주제 관련 키워드 사용 (예: "청자", "불상", "조선시대")
            - search_weather_daily_api: request_context.weather_params(year, month, stn_ids, num_of_rows)을 우선 사용.
            - search_performance_info_api: keyword에 공연 기관명 또는 공연명 사용 (예: "예술의전당", "세종문화회관", "라트라비아타")
            - 각 도구는 num_of_rows 파라미터로 조회할 데이터 개수 조정 가능 (기본: 50개)
            
            # 실행 지침
            1. 반드시 하나 이상의 도구를 호출하여 실제 데이터를 수집하세요
            2. 도구 호출 후 결과를 간략히 요약하세요
            3. 수집한 데이터가 보고서 주제와 어떻게 연관되는지 설명하세요
            4. 구현되지 않은 도구는 호출하지 마세요
            5. 날짜 월 입력이 들어올 경우 반드시 search_weather_daily_api를 호출하세요

            # 출력 지침
            - 도구 호출 후 간단 요약만 남기고, 대용량 본문은 남기지 마세요.

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
        ).partial(
            request_context=json.dumps(request_context, ensure_ascii=False, indent=2),
            organization_name=(request_context.get("organization_name") or ""),
            )

        chain = prompt | llm.bind_tools(tools)
        ai_response = chain.invoke({"messages": messages})
        messages.append(ai_response)

        research_notes = state.get("research_notes")
        research_sources = list(state.get("research_sources", []))
        research_payload = list(state.get("research_payload", []))

        org = (request_context.get("organization_name") or "").strip()
        weather_params = request_context.get("weather_params") or state.get("weather_params") or {}

        called_tools: List[str] = []

        if hasattr(ai_response, "tool_calls"):
            for call in ai_response.tool_calls:
                tool_name = call.get("name")
                tool_args = dict(call.get("args", {}) or {})
                tool_fn = next((t for t in tools if t.name == tool_name), None)
                if tool_fn is None:
                    continue

                
                if tool_name == getattr(toolkit.search_weather_daily_api, "name", "search_weather_daily_api"):
                    merged = {**weather_params, **tool_args}

                elif tool_name in {
                    getattr(toolkit.search_performance_info_api, "name", "search_performance_info_api"),
                    getattr(toolkit.search_exhibition_info_api, "name", "search_exhibition_info_api"),
                }:
                    if not tool_args.get("keyword") and org:
                        tool_args["keyword"] = org

                tool_result = tool_fn.invoke(tool_args)
                called_tools.append(tool_name)

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
                    research_sources.extend(sources)
                    data = tool_result.get("data") or []
                    if data:
                        research_payload.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "count": len(data),
                            "sample": data[:5],  # 과하지 않게 일부만
                        })
                if not called_tools:
            # 공연
                    if org:
                        perf_res = toolkit.search_performance_info_api.invoke({"keyword": org, "num_of_rows": 50})
                        if isinstance(perf_res, dict):
                            n = perf_res.get("notes")
                            if n:
                                entry = f"- {n}"
                                research_notes = f"{research_notes}\n{entry}".strip() if research_notes else entry
                            research_sources.extend(perf_res.get("sources") or [])
                            data = perf_res.get("data") or []
                            if data:
                                research_payload.append({
                                    "tool": getattr(toolkit.search_performance_info_api, "name", "search_performance_info_api"),
                                    "args": {"keyword": org, "num_of_rows": 50},
                                    "count": len(data),
                                    "sample": data[:5],
                                })

                    # 날씨
                    if weather_params.get("year") and weather_params.get("month"):
                        wx_args = {
                            "year": weather_params["year"],
                            "month": weather_params["month"],
                            "stn_ids": weather_params.get("stn_ids", "108"),
                            "num_of_rows": 999,
                        }
                        wx_res = toolkit.search_weather_daily_api.invoke(wx_args)
                        if isinstance(wx_res, dict):
                            n = wx_res.get("notes")
                            if n:
                                entry = f"- {n}"
                                research_notes = f"{research_notes}\n{entry}".strip() if research_notes else entry
                            research_sources.extend(wx_res.get("sources") or [])
                            data = wx_res.get("data") or []
                            if data:
                                research_payload.append({
                                    "tool": getattr(toolkit.search_weather_daily_api, "name", "search_weather_daily_api"),
                                    "args": wx_args,
                                    "count": len(data),
                                    "sample": data[:5],
                                })

        summary_text = getattr(ai_response, "content", "").strip()
        if summary_text:
            research_notes = summary_text if research_notes is None else research_notes

        if not research_notes:
            research_notes = "조사 단계가 초기화되었습니다. 도구 구현이 완료되면 이 부분을 채워 주세요."

        return {
            "messages": messages,
            "research_notes": research_notes,
            "research_sources": research_sources,
            "research_payload": research_payload,
        }

    return search_agent_node
