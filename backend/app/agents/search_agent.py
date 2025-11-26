from __future__ import annotations
import re
import json
import textwrap
import logging
from typing import List
from datetime import datetime

from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agents.db_agent_tools import db_tools, DB_SCHEMA_CONTEXT

logger = logging.getLogger("uvicorn.error")


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
        # 모든 도구 목록 (API + DB)
        all_tools = [
            toolkit.search_exhibition_info_api,      # 전시 정보 API
            toolkit.search_museum_collection_api,    # 소장품 검색 API
            toolkit.search_performance_info_api,     # 공연 정보 API
            # toolkit.get_monthly_age_gender_ratio_data,  # DB Tool로 대체
            # toolkit.get_google_map_rating_statistics,   # DB Tool로 대체
        ] + db_tools  # 범용 DB 쿼리 도구

        def _extract_year_month(text: str):
            m = re.search(r'(\d{4})\s*[-./]?\s*(?:년)?\s*(1[0-2]|0?[1-9])\s*(?:월)?', text)
            if m:
                return int(m.group(1)), int(m.group(2))
            return None, None

        request_context = state.get("request_context", {})
        messages: List = list(state.get("messages", []))
        
        # 날짜 정보 추출
        analysis_target_dates = request_context.get("analysis_target_dates", [])
        is_multi_date_analysis = request_context.get("is_multi_date_analysis", False)
        
        # 기관별 사용 가능한 도구 필터링
        org = (request_context.get("organization_name") or "").strip().lower()
        
        # 모든 도구를 LLM에게 제공 - LLM이 시스템 프롬프트 가이드에 따라 적절한 도구 선택
        tools = all_tools.copy()
        
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
            
            # 데이터베이스 스키마 정보
            {db_schema_context}
            
            # 도구 선택 가이드
            
            ## API 도구 (외부 공공 API)
            - 국립중앙박물관: search_museum_collection_api (소장품 정보 검색)
            - 국립현대미술관, 미술관: search_exhibition_info_api (전시 정보 검색)
            - 예술의전당, 공연장, 콘서트홀: search_performance_info_api (공연 정보 검색)
            
            ## DB 도구 (내부 데이터베이스 조회)
            - search_database: LIKE 검색 (시설명 등)
            - filter_database: 정확한 조건 필터링 (시설ID, 연월 등)
            - query_with_range_filter: 범위 조건 + 검색 조건
            - get_aggregated_statistics: 그룹별 집계 통계
            
            ## 필수 데이터 조회 방법 (DB Tool 사용)
            1. 연령대별 성별 비율: mrcno_demographics 테이블 (cutr_facl_id, cri_ym으로 필터)
            2. 구글맵 평점 통계: google_map_reviews 테이블 (slta_cd로 집계)
            
            # 수집 전략
            1. 요청 컨텍스트의 organization_name(기관명)을 파악하세요
            2. report_topic(보고서 주제)과 questions(질문 목록)을 분석하세요
            3. **첫 번째 호출: API 도구 + DB 도구 동시 호출** (병렬 실행으로 효율성 향상):
               - API 도구: 기관에 맞는 API (박물관→소장품, 미술관→전시, 공연장→공연)
               - DB 도구: facilities에서 시설 검색 + google_map_facilities에서 시설 검색
            4. **두 번째 호출: 상세 데이터 조회** (첫 번째 결과의 ID 사용):
               - mrcno_demographics에서 연령대별 성별 비율 (cutr_facl_id 사용)
               - google_map_reviews에서 평점 통계 집계 (slta_cd 사용)
            5. 불필요한 중복 호출 금지
            
            **중요: 가능한 경우 여러 도구를 한 번에 호출하세요!**
            
            # 도구 호출 가이드
            
            ## API 도구 (외부 공공 API)
            - search_exhibition_info_api: 전시 정보 검색 (keyword에 기관명 사용)
            - search_museum_collection_api: 소장품 검색 (keyword에 주제 사용: 청자, 불상 등)
            - search_performance_info_api: 공연 정보 검색 (keyword에 기관명 또는 공연명)
            
            ## DB 도구 (내부 데이터베이스)
            - search_database: LIKE 검색 (예: 시설명에 "박물관" 포함)
            - filter_database: 정확한 조건 필터링 (JSON 형식, 예: '{{"cri_ym": 202410}}')
              * cri_ym, cutr_facl_id는 INTEGER 타입! 예: 202410 (문자열 아님)
            - query_with_range_filter: 범위 조건 + 검색 조건 동시 적용
            - get_aggregated_statistics: 그룹별 집계 (COUNT, AVG, SUM 등)
            - get_database_schema_info: 테이블/컬럼 정보 조회
            
            ## 필수 데이터 조회 순서
            1. search_database("facilities", "mrc_snbd_nm", "{{기관명}}") → cutr_facl_id 획득
            2. filter_database("mrcno_demographics", '{{"cutr_facl_id": [ID], "cri_ym": [YYYYMM]}}')
            3. search_database("google_map_facilities", "slta_nm", "{{기관명}}") → slta_cd 획득
            4. get_aggregated_statistics("google_map_reviews", "slta_cd", "sns_content_rating", "avg")
            
            # DB 쿼리 도구 사용 가이드 (세부 데이터 조회용)
            위 데이터베이스 스키마 정보를 참고하여 필요한 데이터를 조회하세요.
            
            - search_database: 시설명 등 키워드로 LIKE 검색
              * 예: search_database("facilities", "mrc_snbd_nm", "박물관") → 시설명에 '박물관' 포함된 시설
              * 예: search_database("google_map_facilities", "slta_nm", "국립중앙박물관") → 시설명 검색
            
            - filter_database: 정확한 조건으로 필터링
              * 예: filter_database("mrcno_demographics", '{{"cri_ym": 202410}}') → 2024년 10월 인구통계
              * 예: filter_database("persona_metrics", '{{"cutr_facl_id": "12345678"}}') → 특정 시설 페르소나
            
            - query_with_range_filter: 범위 조건 + 검색 조건 동시 적용
              * 예: query_with_range_filter("persona_metrics", None, None, "cri_ym", 202401, 202412) → 2024년 전체
              * 예: query_with_range_filter("google_map_reviews", "sns_content_original_text", "좋아요", "sns_content_rating", 4, 5) → 4~5점 리뷰 중 '좋아요' 포함
            
            - get_aggregated_statistics: 그룹별 집계 통계
              * 예: get_aggregated_statistics("google_map_reviews", "slta_cd", "id", "count") → 시설별 리뷰 수
              * 예: get_aggregated_statistics("google_map_reviews", "slta_cd", "sns_content_rating", "avg") → 시설별 평균 평점
            
            - get_database_schema_info: 사용 가능한 테이블/컬럼 정보 조회
            
            # 실행 지침
            1. **API와 DB 도구를 동시에 호출하세요** (병렬 호출 권장)
               - 예: search_museum_collection_api + search_database("facilities"...) 동시 호출
            2. 첫 번째 호출 결과에서 ID를 획득한 후, 상세 데이터 조회
            3. 도구 호출 후 결과를 간략히 요약하세요
            4. cri_ym, cutr_facl_id는 INTEGER 타입입니다 (예: 202410)

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
            # API 도구
            "search_exhibition_info_api": "1. search_exhibition_info_api: 전시 정보 검색 (미술관용)",
            "search_museum_collection_api": "2. search_museum_collection_api: 박물관 소장품 검색",
            "search_performance_info_api": "3. search_performance_info_api: 공연 정보 검색 (공연장용)",
            # DB 쿼리 도구
            "search_database": "4. search_database: DB에서 LIKE 검색",
            "filter_database": "5. filter_database: DB에서 정확한 조건 필터링",
            "query_with_range_filter": "6. query_with_range_filter: DB에서 범위 + 검색 조건",
            "get_aggregated_statistics": "7. get_aggregated_statistics: DB에서 그룹별 집계 통계",
            "get_database_schema_info": "8. get_database_schema_info: 테이블/컬럼 정보 조회",
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
            db_schema_context=DB_SCHEMA_CONTEXT,
        )

        chain = prompt | llm.bind_tools(tools)
        
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
        
        # 연속 쿼리 지원: 최대 3회 반복 (Multi-hop Query)
        MAX_TOOL_ITERATIONS = 3
        previous_tool_calls = set()  # 중복 호출 감지용
        
        for iteration in range(MAX_TOOL_ITERATIONS):
            ai_response = chain.invoke({"messages": messages})
            messages.append(ai_response)
            
            # 도구 호출이 없으면 반복 종료
            if not hasattr(ai_response, "tool_calls") or not ai_response.tool_calls:
                logger.info(f"연속 쿼리 종료: {iteration + 1}번째 반복에서 도구 호출 없음")
                break
            
            # 중복 호출 감지: 이전과 동일한 도구+인자면 종료
            current_calls = set()
            for call in ai_response.tool_calls:
                call_signature = f"{call.get('name')}:{json.dumps(call.get('args', {}), sort_keys=True)}"
                current_calls.add(call_signature)
            
            if current_calls == previous_tool_calls:
                logger.info(f"연속 쿼리 종료: {iteration + 1}번째 반복에서 중복 호출 감지")
                # 중복 호출된 ai_response는 ToolMessage가 없으므로 messages에서 제거
                messages.pop()
                break
            
            previous_tool_calls = current_calls
            tool_names = [call.get('name') for call in ai_response.tool_calls]
            logger.info(f"연속 쿼리 {iteration + 1}회차: {len(ai_response.tool_calls)}개 도구 호출 - {tool_names}")
            
            # API 도구 이름 목록 (1회차에만 호출 허용)
            api_tool_names = {
                "search_exhibition_info_api",
                "search_museum_collection_api", 
                "search_performance_info_api",
            }
            
            for call in ai_response.tool_calls:
                tool_name = call.get("name")
                tool_args = dict(call.get("args", {}) or {})
                
                # 2-3회차에서는 API 도구 호출 스킵 (DB 도구만 허용)
                if iteration > 0 and tool_name in api_tool_names:
                    logger.info(f"API 도구 스킵 (2회차 이상): {tool_name}")
                    # 빈 ToolMessage 추가 (OpenAI API 요구사항)
                    messages.append(
                        ToolMessage(
                            tool_call_id=call.get("id"),
                            content="[스킵됨: API 도구는 1회차에만 호출 가능]"
                        )
                    )
                    continue
                
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
                
                # DB 도구 호출 및 결과 로깅
                logger.info(f"도구 호출: {tool_name}, 인자: {tool_args}")
                # 결과가 문자열이면 앞 500자만, dict면 키 목록 출력
                if isinstance(tool_result, str):
                    result_preview = tool_result[:500] + "..." if len(tool_result) > 500 else tool_result
                    logger.info(f"도구 결과 (문자열): {result_preview}")
                elif isinstance(tool_result, dict):
                    logger.info(f"도구 결과 (dict 키): {list(tool_result.keys())}, data 개수: {len(tool_result.get('data', []))}")
                
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
                            # 여러 날짜 분석인 경우, 자동 호출에서 이미 처리했으므로 LLM 호출 결과는 무시
                            if is_multi_date_analysis:
                                logger.info("여러 날짜 분석 모드: 자동 호출에서 이미 처리된 차트 데이터가 있으므로 LLM 호출 결과는 무시합니다.")
                            else:
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
                                            # 기존 데이터가 있으면 병합 (중복 제거)
                                            existing_data = chart_data.get("age_gender_ratio", [])
                                            existing_yms = {item.get("cri_ym") for item in existing_data if item.get("cri_ym")}
                                            
                                            new_data = [item for item in filtered_data if item.get("cri_ym") not in existing_yms]
                                            if new_data:
                                                chart_data["age_gender_ratio"] = existing_data + new_data
                                                logger.info(f"차트 데이터 저장 완료: {requested_year}년 {requested_month}월 데이터 (필터링: {len(chart_data_value)}개월 → {len(filtered_data)}개월, 병합: {len(existing_data)}개월 + {len(new_data)}개월)")
                                            elif filtered_data[0].get("cri_ym") in existing_yms:
                                                logger.info(f"차트 데이터 중복: {requested_year}년 {requested_month}월 데이터는 이미 존재합니다.")
                                            else:
                                                chart_data["age_gender_ratio"] = filtered_data
                                                logger.info(f"차트 데이터 저장 완료: {requested_year}년 {requested_month}월 데이터 (필터링: {len(chart_data_value)}개월 → {len(filtered_data)}개월)")
                                        else:
                                            logger.warning(f"요청한 {requested_year}년 {requested_month}월 데이터가 없습니다.")
                                    else:
                                        # 전체 기간을 요청한 경우, analysis_target_dates에 해당하는 데이터만 필터링
                                        if analysis_target_dates and len(analysis_target_dates) > 0:
                                            # analysis_target_dates에 해당하는 데이터만 필터링
                                            target_yms = {date_str.replace('-', '') for date_str in analysis_target_dates}
                                            filtered_data = [item for item in chart_data_value if item.get("cri_ym") in target_yms]
                                            
                                            if filtered_data:
                                                # 기존 데이터와 병합 (중복 제거)
                                                existing_data = chart_data.get("age_gender_ratio", [])
                                                existing_yms = {item.get("cri_ym") for item in existing_data if item.get("cri_ym")}
                                                
                                                new_data = [item for item in filtered_data if item.get("cri_ym") not in existing_yms]
                                                if new_data:
                                                    chart_data["age_gender_ratio"] = existing_data + new_data
                                                    logger.info(f"차트 데이터 필터링 및 병합 완료: {len(chart_data_value)}개월 → {len(filtered_data)}개월 (필터링), 기존 {len(existing_data)}개월 + 신규 {len(new_data)}개월 = 총 {len(chart_data['age_gender_ratio'])}개월")
                                                else:
                                                    logger.info(f"차트 데이터 중복: 필터링된 {len(filtered_data)}개월 데이터는 이미 존재합니다.")
                                            else:
                                                logger.warning(f"analysis_target_dates {analysis_target_dates}에 해당하는 데이터가 없습니다.")
                                        else:
                                            # analysis_target_dates가 없으면 기존 로직 유지
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
        
        # LLM이 도구를 호출하지 않았을 때 기본 안내
        if not called_tools:
            logger.info("LLM이 도구를 호출하지 않음 - 기본 안내 추가")
            research_notes = research_notes or "데이터 조회가 필요합니다."

        summary_text = getattr(ai_response, "content", "").strip()
        if summary_text:
            research_notes = summary_text if research_notes is None else research_notes

        if not research_notes:
            research_notes = "조사 단계가 초기화되었습니다. 도구 구현이 완료되면 이 부분을 채워 주세요."

        # 토큰 절약: ToolMessage 내용을 요약으로 축약 (상세 데이터는 research_payload에 저장됨)
        for i, msg in enumerate(messages):
            if isinstance(msg, ToolMessage):
                try:
                    content = msg.content
                    if content and len(content) > 200:
                        # JSON 파싱 시도
                        parsed = json.loads(content)
                        if isinstance(parsed, list):
                            summary = f"[결과 {len(parsed)}개 - 상세는 research_payload 참조]"
                        elif isinstance(parsed, dict):
                            if "error" in parsed:
                                summary = f"[오류: {str(parsed.get('error', ''))[:100]}]"
                            elif "data" in parsed:
                                data_count = len(parsed.get("data", []))
                                summary = f"[결과 {data_count}개 - 상세는 research_payload 참조]"
                            else:
                                summary = f"[dict 결과 - 키: {list(parsed.keys())[:5]}]"
                        else:
                            summary = content[:200] + "..."
                        
                        # ToolMessage는 불변이므로 새로 생성
                        messages[i] = ToolMessage(
                            tool_call_id=msg.tool_call_id,
                            content=summary
                        )
                except (json.JSONDecodeError, Exception):
                    # 파싱 실패 시 앞부분만 유지
                    if len(msg.content) > 200:
                        messages[i] = ToolMessage(
                            tool_call_id=msg.tool_call_id,
                            content=msg.content[:200] + "..."
                        )
        
        logger.info(f"ToolMessage 축약 완료: messages 개수 {len(messages)}")

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
