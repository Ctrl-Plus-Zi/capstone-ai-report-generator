from __future__ import annotations
import re
import json
import textwrap
import logging
from typing import List
from datetime import datetime

from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

logger = logging.getLogger(__name__)


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
        # 기본 도구 목록 (날씨 API 제거)
        all_tools = [
            toolkit.search_exhibition_info_api,
            toolkit.search_museum_collection_api,
            toolkit.search_performance_info_api,
            toolkit.get_monthly_age_gender_ratio_data,  # 월별 연령대별 성별 비율 데이터 조회
            toolkit.get_google_map_rating_statistics,  # 구글맵 리뷰 평점 통계 조회
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
        
        # 연령대별 성별 비율 데이터 조회 도구는 모든 기관에서 사용 가능
        if toolkit.get_monthly_age_gender_ratio_data not in tools:
            tools.append(toolkit.get_monthly_age_gender_ratio_data)
        
        # 날짜 필터링 변수 (함수 전체에서 사용)
        current_date = request_context.get("current_date", "")
        filter_active = request_context.get("filter_active_only", False)

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
            - get_monthly_age_gender_ratio_data: 모든 기관에서 사용 가능 (월별 연령대별 성별 비율 데이터)
            
            # 수집 전략
            1. 요청 컨텍스트의 organization_name(기관명)을 파악하세요
            2. 위의 기관별 API 사용 규칙을 반드시 준수하세요. 해당 기관에 맞지 않는 API는 호출하지 마세요.
            3. report_topic(보고서 주제)과 questions(질문 목록)을 분석하세요
            4. **필수 도구 호출 (반드시 실행)**:
               a. get_monthly_age_gender_ratio_data: 
                  - 질문에 "2025년 1월", "2025 1월", "2025-01", "분석 기간: 2025년 2월" 같은 날짜가 포함되어 있으면 해당 월의 데이터를 조회
                  - 예: "2025년 2월"이면 organization_name="{organization_name}", year=2025, month=2로 호출
                  - 날짜가 없어도 연령대별 성별 비율 데이터는 보고서에 필수이므로 반드시 호출하세요 (year=None, month=None으로 전체 기간 조회 가능)
                  - 이 도구는 모든 기관에서 사용 가능합니다 (국립현대미술관, 예술의전당, 국립중앙박물관 모두)
               b. get_google_map_rating_statistics:
                  - 모든 보고서에서 고객 만족도 분석을 위해 반드시 호출하세요
                  - 예: organization_name="{organization_name}"로 호출
                  - 모든 기관에서 사용 가능하며, 보고서에 평점 통계가 포함되어야 합니다
            5. 요청 컨텍스트에 current_date(현재 날짜)가 있으면, 현재 진행 중인 공연/전시만 필터링하세요
               - filter_active_only가 True인 경우, 오늘 날짜({current_date}) 기준으로 진행 중인 것만 수집
               - PERIOD 또는 EVENT_PERIOD 필드를 확인하여 오늘 날짜가 기간 내에 있는지 검증
               - 과거 공연/전시나 미래 예정 공연은 제외하고 현재 진행 중인 것만 포함
            6. 검색 키워드는 organization_name과 questions에서 추출하세요
            7. 불필요한 대량 호출/중복 호출 금지
            
            # 도구 호출 가이드
            - search_exhibition_info_api: keyword에 기관명 사용 (예: "국립현대미술관", "국립중앙박물관")
            - search_museum_collection_api: keyword에 주제 관련 키워드 사용 (예: "청자", "불상", "조선시대")
            - search_performance_info_api: keyword에 공연 기관명 또는 공연명 사용 (예: "예술의전당", "세종문화회관", "라트라비아타")
            - get_monthly_age_gender_ratio_data: AWS RDS에서 월별 남성/여성 연령대 비율 데이터 조회
              * 질문에 "2025년 1월", "2025 1월", "2025-01" 같은 날짜가 포함되어 있으면 해당 월의 데이터를 조회하세요
              * 예: organization_name="국립현대미술관", year=2025, month=1
              * 날짜가 없으면 전체 기간 데이터를 조회하세요 (year=None, month=None)
            - get_google_map_rating_statistics: AWS RDS에서 구글맵 리뷰 평점 통계 조회
              * 기관별 구글맵 리뷰의 평점 분포와 평균 평점을 계산하여 반환
              * 예: organization_name="국립현대미술관"
              * 모든 기관에서 사용 가능하며, 고객 만족도 분석에 유용합니다
            - 각 도구는 num_of_rows 파라미터로 조회할 데이터 개수 조정 가능 (기본: 50개)
            
            # 실행 지침
            1. **반드시 다음 도구들을 호출하세요**:
               - get_monthly_age_gender_ratio_data: 연령대별 성별 비율 데이터 (필수)
               - get_google_map_rating_statistics: 구글맵 리뷰 평점 통계 (필수)
               - 기관별 API (국립현대미술관: search_exhibition_info_api, 예술의전당: search_performance_info_api 등)
            2. 도구 호출 후 결과를 간략히 요약하세요
            3. 수집한 데이터가 보고서 주제와 어떻게 연관되는지 설명하세요
            4. 구현되지 않은 도구는 호출하지 마세요
            5. 날씨 데이터는 선택사항이며, 필요할 때만 호출하세요

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
            "search_performance_info_api": "3. search_performance_info_api: 공연 정보 검색 (TITLE, PERIOD, CHARGE, GENRE 등)",
            "search_internal_documents": "4. search_internal_documents: 내부 문서 검색 (구현 예정)",
            "fetch_data_snapshot": "5. fetch_data_snapshot: 데이터 스냅샷 가져오기 (구현 예정)",
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
        chart_data = state.get("chart_data", {})
        rating_statistics = state.get("rating_statistics")
        latest_performance_image = state.get("latest_performance_image", "")

        org = (request_context.get("organization_name") or "").strip()

        called_tools: List[str] = []
        
        # 필수 DB 데이터 자동 호출 여부 추적
        age_gender_called = False
        rating_stats_called = False

        if hasattr(ai_response, "tool_calls"):
            for call in ai_response.tool_calls:
                tool_name = call.get("name")
                tool_args = dict(call.get("args", {}) or {})
                tool_fn = next((t for t in tools if t.name == tool_name), None)
                if tool_fn is None:
                    continue

                # 필수 DB 데이터 호출 여부 추적
                if tool_name == getattr(toolkit.get_monthly_age_gender_ratio_data, "name", "get_monthly_age_gender_ratio_data"):
                    age_gender_called = True
                if tool_name == getattr(toolkit.get_google_map_rating_statistics, "name", "get_google_map_rating_statistics"):
                    rating_stats_called = True

                if tool_name in {
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
                    
                    # 차트 데이터 추출 (월별 연령대별 성별 비율 등)
                    if "chart_data" in tool_result and tool_result["chart_data"]:
                        tool_name_attr = getattr(toolkit.get_monthly_age_gender_ratio_data, "name", "get_monthly_age_gender_ratio_data")
                        if tool_name == tool_name_attr:
                            chart_data_value = tool_result["chart_data"]
                            if chart_data_value:  # 빈 리스트가 아닌 경우만
                                # 특정 월을 요청한 경우 해당 월만 필터링
                                requested_year = tool_args.get("year")
                                requested_month = tool_args.get("month")
                                
                                if requested_year and requested_month:
                                    # 특정 년월을 요청한 경우 해당 월만 필터링
                                    target_ym = f"{requested_year}{requested_month:02d}"
                                    filtered_data = [item for item in chart_data_value if item.get("cri_ym") == target_ym]
                                    if filtered_data:
                                        chart_data["age_gender_ratio"] = filtered_data
                                        logger.info(f"차트 데이터 저장 완료: {requested_year}년 {requested_month}월 데이터 (필터링: {len(chart_data_value)}개월 → {len(filtered_data)}개월)")
                                    else:
                                        logger.warning(f"요청한 {requested_year}년 {requested_month}월 데이터가 없습니다.")
                                        chart_data["age_gender_ratio"] = []
                                else:
                                    # 전체 기간을 요청한 경우, 기존 데이터와 병합 (중복 제거)
                                    existing_data = chart_data.get("age_gender_ratio", [])
                                    existing_yms = {item.get("cri_ym") for item in existing_data if item.get("cri_ym")}
                                    
                                    new_data = []
                                    for item in chart_data_value:
                                        cri_ym = item.get("cri_ym")
                                        if cri_ym and cri_ym not in existing_yms:
                                            new_data.append(item)
                                            existing_yms.add(cri_ym)
                                    
                                    if new_data:
                                        chart_data["age_gender_ratio"] = existing_data + new_data
                                        logger.info(f"차트 데이터 병합 완료: 기존 {len(existing_data)}개월 + 신규 {len(new_data)}개월 = 총 {len(chart_data['age_gender_ratio'])}개월")
                                    else:
                                        # 중복이 없으면 그대로 저장
                                        chart_data["age_gender_ratio"] = chart_data_value
                                        logger.info(f"차트 데이터 저장 완료: {len(chart_data_value)}개월 데이터")
                            else:
                                logger.warning("차트 데이터가 비어있습니다.")
                    
                    # 평점 통계 데이터 추출
                    if "rating_statistics" in tool_result and tool_result["rating_statistics"]:
                        tool_name_attr = getattr(toolkit.get_google_map_rating_statistics, "name", "get_google_map_rating_statistics")
                        if tool_name == tool_name_attr:
                            rating_stats = tool_result["rating_statistics"]
                            if rating_stats and isinstance(rating_stats, dict) and rating_stats.get("total_reviews", 0) > 0:
                                rating_statistics = rating_stats
                                logger.info(f"평점 통계 저장 완료: 총 {rating_stats.get('total_reviews')}개 리뷰")
                            else:
                                logger.warning("평점 통계 데이터가 없거나 리뷰가 없습니다.")
                    
                    # 공연 정보 또는 전시 정보인 경우 가장 최근 이미지 추출
                    if tool_name in {
                        getattr(toolkit.search_performance_info_api, "name", "search_performance_info_api"),
                        getattr(toolkit.search_exhibition_info_api, "name", "search_exhibition_info_api"),
                    } and data:
                        def extract_date_from_period(period_str):
                            """PERIOD 또는 EVENT_PERIOD에서 종료 날짜 추출"""
                            if not period_str:
                                return None
                            try:
                                # 다양한 구분자 처리: "~", " - ", "-"
                                for sep in ["~", " - ", "-"]:
                                    if sep in period_str:
                                        parts = period_str.split(sep, 1)
                                        if len(parts) == 2:
                                            end_str = parts[1].strip().replace(".", "-").replace("/", "-")
                                            # 날짜 형식 정규화
                                            end_str = re.sub(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', r'\1-\2-\3', end_str)
                                            # 월/일이 한 자리 수인 경우 0 패딩
                                            end_parts = end_str.split("-")
                                            if len(end_parts) == 3:
                                                end_str = f"{end_parts[0]}-{end_parts[1].zfill(2)}-{end_parts[2].zfill(2)}"
                                            try:
                                                return datetime.strptime(end_str, "%Y-%m-%d")
                                            except:
                                                continue
                            except:
                                pass
                            return None
                        
                        # 이미지가 있는 공연 중 가장 최근 종료일을 가진 공연 찾기
                        performance_with_images = []
                        for item in data:
                            image_url = item.get("IMAGE_OBJECT") or item.get("image_object") or item.get("IMAGE") or item.get("image")
                            if image_url:
                                period = item.get("PERIOD") or item.get("EVENT_PERIOD") or item.get("period") or item.get("event_period")
                                end_date = extract_date_from_period(period)
                                if end_date:
                                    performance_with_images.append((end_date, image_url, item.get("TITLE") or item.get("title", "")))
                        
                        if performance_with_images:
                            # 종료일 기준으로 내림차순 정렬 (가장 최근이 첫 번째)
                            performance_with_images.sort(key=lambda x: x[0], reverse=True)
                            latest_performance_image = performance_with_images[0][1]
                    
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
                            
                            # 공연 정보 또는 전시 정보인 경우 가장 최근 이미지 추출
                            if data and not latest_performance_image:
                                def extract_date_from_period(period_str):
                                    """PERIOD 또는 EVENT_PERIOD에서 종료 날짜 추출"""
                                    if not period_str:
                                        return None
                                    try:
                                        for sep in ["~", " - ", "-"]:
                                            if sep in period_str:
                                                parts = period_str.split(sep, 1)
                                                if len(parts) == 2:
                                                    end_str = parts[1].strip().replace(".", "-").replace("/", "-")
                                                    end_str = re.sub(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', r'\1-\2-\3', end_str)
                                                    end_parts = end_str.split("-")
                                                    if len(end_parts) == 3:
                                                        end_str = f"{end_parts[0]}-{end_parts[1].zfill(2)}-{end_parts[2].zfill(2)}"
                                                    try:
                                                        return datetime.strptime(end_str, "%Y-%m-%d")
                                                    except:
                                                        continue
                                    except:
                                        pass
                                    return None
                                
                                performance_with_images = []
                                for item in data:
                                    image_url = item.get("IMAGE_OBJECT") or item.get("image_object") or item.get("IMAGE") or item.get("image")
                                    if image_url:
                                        period = item.get("PERIOD") or item.get("EVENT_PERIOD") or item.get("period") or item.get("event_period")
                                        end_date = extract_date_from_period(period)
                                        if end_date:
                                            performance_with_images.append((end_date, image_url, item.get("TITLE") or item.get("title", "")))
                                
                                if performance_with_images:
                                    performance_with_images.sort(key=lambda x: x[0], reverse=True)
                                    latest_performance_image = performance_with_images[0][1]
                            
                            if data:
                                research_payload.append({
                                    "tool": getattr(toolkit.search_performance_info_api, "name", "search_performance_info_api"),
                                    "args": {"keyword": org, "num_of_rows": 50},
                                    "count": len(data),
                                    "sample": data[:5],
                                })

                    # 날씨 API 제거됨

        # 필수 DB 데이터 자동 호출 (LLM이 호출하지 않은 경우)
        # 1. 연령대별 성별 비율 데이터 자동 호출
        if not age_gender_called:
            logger.info("연령대별 성별 비율 데이터 자동 호출 시작")
            try:
                # 질문에서 년월 추출
                user_text = " ".join([m.content for m in messages if getattr(m, "content", None)])
                year, month = _extract_year_month(user_text)
                
                # request_context에서도 년월 확인
                if not year or not month:
                    year = request_context.get("current_year")
                    month = request_context.get("current_month")
                
                age_gender_args = {
                    "organization_name": org,
                    "year": year,
                    "month": month,
                }
                
                age_gender_result = toolkit.get_monthly_age_gender_ratio_data.invoke(age_gender_args)
                called_tools.append(getattr(toolkit.get_monthly_age_gender_ratio_data, "name", "get_monthly_age_gender_ratio_data"))
                
                if isinstance(age_gender_result, dict):
                    notes = age_gender_result.get("notes", "")
                    if notes:
                        note_entry = f"- {notes} (자동 호출)"
                        research_notes = f"{research_notes}\n{note_entry}".strip() if research_notes else note_entry
                    
                    # 차트 데이터 즉시 저장
                    if "chart_data" in age_gender_result and age_gender_result["chart_data"]:
                        chart_data_value = age_gender_result["chart_data"]
                        if chart_data_value:
                            # 특정 월을 요청한 경우 해당 월만 필터링
                            if year and month:
                                # 특정 년월을 요청한 경우 해당 월만 필터링
                                target_ym = f"{year}{month:02d}"
                                filtered_data = [item for item in chart_data_value if item.get("cri_ym") == target_ym]
                                if filtered_data:
                                    chart_data["age_gender_ratio"] = filtered_data
                                    logger.info(f"차트 데이터 자동 저장 완료: {year}년 {month}월 데이터 (필터링: {len(chart_data_value)}개월 → {len(filtered_data)}개월)")
                                else:
                                    logger.warning(f"요청한 {year}년 {month}월 데이터가 없습니다.")
                                    chart_data["age_gender_ratio"] = []
                            else:
                                # 전체 기간을 요청한 경우 그대로 저장
                                chart_data["age_gender_ratio"] = chart_data_value
                                logger.info(f"차트 데이터 자동 저장 완료: {len(chart_data_value)}개월 데이터")
                        else:
                            logger.warning("차트 데이터가 비어있습니다.")
                    
                    # ToolMessage는 추가하지 않음 (데이터는 state에 저장되므로 분석 에이전트가 state에서 읽음)
                    # 잘못된 tool_call_id로 인한 OpenAI API 에러 방지
            except Exception as e:
                logger.error(f"연령대별 성별 비율 데이터 자동 호출 실패: {e}", exc_info=True)
        
        # 2. 구글맵 리뷰 평점 통계 자동 호출
        if not rating_stats_called:
            logger.info("구글맵 리뷰 평점 통계 자동 호출 시작")
            try:
                rating_args = {
                    "organization_name": org,
                }
                
                rating_result = toolkit.get_google_map_rating_statistics.invoke(rating_args)
                called_tools.append(getattr(toolkit.get_google_map_rating_statistics, "name", "get_google_map_rating_statistics"))
                
                if isinstance(rating_result, dict):
                    notes = rating_result.get("notes", "")
                    if notes:
                        note_entry = f"- {notes} (자동 호출)"
                        research_notes = f"{research_notes}\n{note_entry}".strip() if research_notes else note_entry
                    
                    # 평점 통계 즉시 저장
                    if "rating_statistics" in rating_result and rating_result["rating_statistics"]:
                        rating_stats = rating_result["rating_statistics"]
                        if rating_stats and isinstance(rating_stats, dict) and rating_stats.get("total_reviews", 0) > 0:
                            rating_statistics = rating_stats
                            logger.info(f"평점 통계 자동 저장 완료: 총 {rating_stats.get('total_reviews')}개 리뷰")
                        else:
                            logger.warning("평점 통계 데이터가 없거나 리뷰가 없습니다.")
                    
                    # ToolMessage는 추가하지 않음 (데이터는 state에 저장되므로 분석 에이전트가 state에서 읽음)
                    # 잘못된 tool_call_id로 인한 OpenAI API 에러 방지
            except Exception as e:
                logger.error(f"구글맵 리뷰 평점 통계 자동 호출 실패: {e}", exc_info=True)

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
            "latest_performance_image": latest_performance_image,
            "chart_data": chart_data,
            "rating_statistics": rating_statistics,
        }

    return search_agent_node
