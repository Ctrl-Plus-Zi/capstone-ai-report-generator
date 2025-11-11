from __future__ import annotations
import re
import json
import textwrap
from typing import List
from datetime import datetime

from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


# 보고서 초안을 위한 자료를 수집하는 조사 에이전트 노드 생성 
def create_search_agent(llm, toolkit):

    def _filter_by_current_date(data: List[dict], current_date: str, date_fields: List[str] = None) -> List[dict]:
        """현재 날짜 기준으로 진행 중인 공연/전시만 필터링"""
        if not current_date or not data:
            return data
        
        if date_fields is None:
            date_fields = ["PERIOD", "EVENT_PERIOD", "period", "event_period"]
        
        try:
            today = datetime.strptime(current_date, "%Y-%m-%d")
        except:
            return data  # 날짜 파싱 실패 시 필터링 안 함
        
        filtered = []
        for item in data:
            is_active = False
            for field in date_fields:
                period_str = item.get(field)
                if not period_str:
                    continue
                
                # 날짜 범위 파싱 (예: "2024-01-01~2024-12-31" 또는 "2024.01.01 - 2024.12.31")
                period_str = period_str.strip()
                # 다양한 구분자 처리
                for sep in ["~", " - ", "-", "~"]:
                    if sep in period_str:
                        parts = period_str.split(sep, 1)
                        if len(parts) == 2:
                            try:
                                start_str = parts[0].strip().replace(".", "-").replace("/", "-")
                                end_str = parts[1].strip().replace(".", "-").replace("/", "-")
                                
                                # 날짜 형식 정규화 (YYYY-MM-DD 형식으로)
                                start_str = re.sub(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', r'\1-\2-\3', start_str)
                                end_str = re.sub(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', r'\1-\2-\3', end_str)
                                
                                # 월/일이 한 자리 수인 경우 0 패딩
                                start_parts = start_str.split("-")
                                if len(start_parts) == 3:
                                    start_str = f"{start_parts[0]}-{start_parts[1].zfill(2)}-{start_parts[2].zfill(2)}"
                                end_parts = end_str.split("-")
                                if len(end_parts) == 3:
                                    end_str = f"{end_parts[0]}-{end_parts[1].zfill(2)}-{end_parts[2].zfill(2)}"
                                
                                start_date = datetime.strptime(start_str, "%Y-%m-%d")
                                end_date = datetime.strptime(end_str, "%Y-%m-%d")
                                
                                if start_date <= today <= end_date:
                                    is_active = True
                                    break
                            except:
                                continue
                        break
            
            if is_active:
                filtered.append(item)
        
        return filtered if filtered else data  # 필터링 결과가 없으면 원본 반환 (최소한의 데이터라도 유지)

    def search_agent_node(state):
        # 기본 도구 목록
        all_tools = [
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
        
        # 기관별 사용 가능한 도구 필터링
        org = (request_context.get("organization_name") or "").strip().lower()
        
        # 기관별 API 매핑
        org_api_mapping = {
            "국립중앙박물관": [toolkit.search_museum_collection_api],
            "국립현대미술관": [toolkit.search_exhibition_info_api],
            "예술의전당": [toolkit.search_performance_info_api],
            "예술의 전당": [toolkit.search_performance_info_api],
        }
        
        # 기관명 매칭 (부분 일치 포함)
        tools = []
        for org_key, allowed_tools in org_api_mapping.items():
            if org_key.lower() in org or org in org_key.lower():
                tools = allowed_tools.copy()
                break
        
        # 매칭되지 않으면 모든 도구 사용 (기존 동작 유지)
        if not tools:
            tools = all_tools.copy()
        
        # 날씨 API는 항상 사용 가능 (요청이 있을 때만 사용)
        if toolkit.search_weather_daily_api not in tools:
            tools.append(toolkit.search_weather_daily_api)
        
        # 날짜 필터링 변수 (함수 전체에서 사용)
        current_date = request_context.get("current_date", "")
        filter_active = request_context.get("filter_active_only", False)

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
            
            # 사용 가능한 도구 (기관별로 제한됨)
            {available_tools_description}
            
            # 기관별 API 사용 규칙 (중요!)
            - 국립중앙박물관: search_museum_collection_api만 사용 (소장품 정보)
            - 국립현대미술관: search_exhibition_info_api만 사용 (전시 정보)
            - 예술의전당: search_performance_info_api만 사용 (공연 정보)
            - 날씨 데이터가 필요한 경우에만 search_weather_daily_api 사용 (모든 기관 공통)
            
            # 수집 전략
            1. 요청 컨텍스트의 organization_name(기관명)을 파악하세요
            2. 위의 기관별 API 사용 규칙을 반드시 준수하세요. 해당 기관에 맞지 않는 API는 호출하지 마세요.
            3. report_topic(보고서 주제)과 questions(질문 목록)을 분석하세요
            4. 요청 컨텍스트에 current_date(현재 날짜)가 있으면, 현재 진행 중인 공연/전시만 필터링하세요
               - filter_active_only가 True인 경우, 오늘 날짜({current_date}) 기준으로 진행 중인 것만 수집
               - PERIOD 또는 EVENT_PERIOD 필드를 확인하여 오늘 날짜가 기간 내에 있는지 검증
               - 과거 공연/전시나 미래 예정 공연은 제외하고 현재 진행 중인 것만 포함
            5. 검색 키워드는 organization_name과 questions에서 추출하세요
            6. 불필요한 대량 호출/중복 호출 금지
            
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

        current_date = request_context.get("current_date", "")
        filter_active = request_context.get("filter_active_only", False)
        
        # 사용 가능한 도구 설명 생성
        available_tools_list = []
        tool_descriptions = {
            "search_exhibition_info_api": "1. search_exhibition_info_api: 문화시설의 전시 정보 검색 (TITLE, PERIOD, DESCRIPTION, URL, CHARGE 등)",
            "search_museum_collection_api": "2. search_museum_collection_api: 박물관 소장품 정보 검색 (title, description, artist, issuedDate 등)",
            "search_weather_daily_api": "3. search_weather_daily_api: 기상청 ASOS 일자료(일별)를 월 단위로 조회 (tm, sumRn, maxTa, minTa 등)",
            "search_performance_info_api": "4. search_performance_info_api: 공연 정보 검색 (TITLE, PERIOD, CHARGE, GENRE 등)",
            "search_internal_documents": "5. search_internal_documents: 내부 문서 검색 (구현 예정)",
            "fetch_data_snapshot": "6. fetch_data_snapshot: 데이터 스냅샷 가져오기 (구현 예정)",
        }
        
        for tool in tools:
            tool_name = getattr(tool, "name", "")
            if tool_name in tool_descriptions:
                available_tools_list.append(tool_descriptions[tool_name])
        
        available_tools_description = "\n".join(available_tools_list) if available_tools_list else "사용 가능한 도구가 없습니다."
        
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_text),
                MessagesPlaceholder(variable_name="messages"),
            ]
        ).partial(
            request_context=json.dumps(request_context, ensure_ascii=False, indent=2),
            organization_name=(request_context.get("organization_name") or ""),
            current_date=current_date if current_date else "날짜 정보 없음",
            available_tools_description=available_tools_description,
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
                
                # 날짜 필터링 적용 (공연/전시 정보인 경우)
                if isinstance(tool_result, dict):
                    current_date = request_context.get("current_date")
                    filter_active = request_context.get("filter_active_only", False)
                    
                    if filter_active and current_date and tool_name in {
                        getattr(toolkit.search_performance_info_api, "name", "search_performance_info_api"),
                        getattr(toolkit.search_exhibition_info_api, "name", "search_exhibition_info_api"),
                    }:
                        original_data = tool_result.get("data", [])
                        if original_data:
                            filtered_data = _filter_by_current_date(original_data, current_date)
                            if len(filtered_data) < len(original_data):
                                tool_result["data"] = filtered_data
                                tool_result["count"] = len(filtered_data)
                                # notes 업데이트
                                original_notes = tool_result.get("notes", "")
                                tool_result["notes"] = f"{original_notes} (날짜 필터링: {len(original_data)}개 → {len(filtered_data)}개)"

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
                        # 날짜 필터링 적용
                        if isinstance(perf_res, dict) and filter_active and current_date:
                            original_data = perf_res.get("data", [])
                            if original_data:
                                filtered_data = _filter_by_current_date(original_data, current_date)
                                if len(filtered_data) < len(original_data):
                                    perf_res["data"] = filtered_data
                                    perf_res["count"] = len(filtered_data)
                                    original_notes = perf_res.get("notes", "")
                                    perf_res["notes"] = f"{original_notes} (날짜 필터링: {len(original_data)}개 → {len(filtered_data)}개)"
                        
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
