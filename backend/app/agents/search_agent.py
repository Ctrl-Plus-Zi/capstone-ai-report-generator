"""
Search Agent - 데이터 수집 에이전트

워크플로우:
    1. DB 쿼리 계획 생성 (LLM) + 계획 설명 저장
    2. API 도구 선택 (LLM) + 호출 이유 저장
    3. DB 쿼리 실행 (기본 계획 + LLM 생성 쿼리)
    4. API 호출 실행
    5. 계획 설명 + 실행 결과를 research_payload에 저장
"""
from __future__ import annotations
import re
import json
import textwrap
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate

from app.agents.db_agent_tools import DB_SCHEMA_CONTEXT
from app.agents.query_executor import execute_data_queries
from app.agents.query_bundle_loader import get_all_for_org
from app.agents import api_bundle_loader

logger = logging.getLogger("uvicorn.error")


def create_search_agent(llm, toolkit):
    """Search Agent 노드 생성"""

    def _filter_by_current_date(data: List[dict], current_date: str) -> List[dict]:
        """현재 날짜 기준 진행 중인 공연/전시 필터링"""
        if not current_date or not data:
            return data
        
        date_fields = ["PERIOD", "EVENT_PERIOD", "period", "event_period"]
        
        try:
            today = datetime.strptime(current_date, "%Y-%m-%d")
        except:
            return data
        
        filtered = []
        for item in data:
            for field in date_fields:
                period_str = item.get(field)
                if not period_str:
                    continue
                
                for sep in ["~", " - ", "-"]:
                    if sep in str(period_str):
                        parts = str(period_str).split(sep, 1)
                        if len(parts) == 2:
                            try:
                                end_str = parts[1].strip().replace(".", "-").replace("/", "-")
                                end_str = re.sub(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', r'\1-\2-\3', end_str)
                                end_parts = end_str.split("-")
                                if len(end_parts) == 3:
                                    end_str = f"{end_parts[0]}-{end_parts[1].zfill(2)}-{end_parts[2].zfill(2)}"
                                end_date = datetime.strptime(end_str, "%Y-%m-%d")
                                if today <= end_date:
                                    filtered.append(item)
                                    break
                            except:
                                continue
                        break
                else:
                    continue
                break
        
        return filtered if filtered else data

    def _extract_latest_image(data: List[dict]) -> str:
        """최신 이미지 URL 추출"""
        if not data:
            return ""
        
        def extract_date(period_str):
            if not period_str:
                return None
            try:
                for sep in ["~", " - ", "-"]:
                    if sep in str(period_str):
                        parts = str(period_str).split(sep, 1)
                        if len(parts) == 2:
                            end_str = parts[1].strip().replace(".", "-").replace("/", "-")
                            end_str = re.sub(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', r'\1-\2-\3', end_str)
                            end_parts = end_str.split("-")
                            if len(end_parts) == 3:
                                end_str = f"{end_parts[0]}-{end_parts[1].zfill(2)}-{end_parts[2].zfill(2)}"
                            return datetime.strptime(end_str, "%Y-%m-%d")
            except:
                pass
            return None
        
        with_images = []
        for item in data:
            image_url = item.get("IMAGE_OBJECT") or item.get("image_object") or item.get("IMAGE") or item.get("image")
            if image_url:
                period = item.get("PERIOD") or item.get("EVENT_PERIOD") or item.get("period")
                end_date = extract_date(period)
                if end_date:
                    with_images.append((end_date, image_url))
        
        if with_images:
            with_images.sort(key=lambda x: x[0], reverse=True)
            return with_images[0][1]
        return ""

    def search_agent_node(state):
        request_context = state.get("request_context", {})
        messages: List = list(state.get("messages", []))
        
        org_name = request_context.get("organization_name", "")
        report_topic = request_context.get("report_topic", "")
        current_date = request_context.get("current_date", "")
        
        research_payload = list(state.get("research_payload", []))
        latest_performance_image = state.get("latest_performance_image", "")

        logger.info(f"[SEARCH_AGENT] ====== 시작 ======")
        logger.info(f"[SEARCH_AGENT] state: {state}")
        logger.info(f"[SEARCH_AGENT] 기관명: {org_name}")
        logger.info(f"[SEARCH_AGENT] 보고서 주제: {report_topic}")

        # 단계 1: DB 쿼리 계획
        logger.info(f"[SEARCH_AGENT] [단계1] DB 쿼리 계획 LLM 호출")
        
        escaped_schema = DB_SCHEMA_CONTEXT.replace('{', '{{').replace('}', '}}')
        
        query_examples = """
## 쿼리 예시

### SNS버즈 시설 검색 -> slta_cd 획득 (구글맵 리뷰용)
{"action": "search", "table": "sns_buzz_master_tbl", "params": {"search_column": "slta_nm", "search_value": "기관명"}, "save_as": "facility"}

### 구글맵 리뷰 조회 (slta_cd 사용)
{"action": "filter", "table": "sns_buzz_extract_contents", "params": {"filters": {"slta_cd": "{facility.slta_cd}"}, "limit": 100}, "save_as": "reviews"}

### LG U+ API에서 시설 검색 -> cutr_facl_id 획득 (인구통계용)
{"action": "search", "table": "lguplus_dpg_api_tot", "params": {"search_column": "cutr_facl_all_nm", "search_value": "기관명"}, "save_as": "lgu_facility"}

### LG U+ 방문자 통계 조회
{"action": "filter", "table": "lguplus_dpg_api_tot", "params": {"filters": {"cutr_facl_id": "{lgu_facility.cutr_facl_id}"}, "limit": 12}, "save_as": "demographics"}

### LG U+ 페르소나 조회
{"action": "filter", "table": "lguplus_dpg_persona_tot", "params": {"filters": {"cutr_facl_id": "{lgu_facility.cutr_facl_id}"}, "limit": 12}, "save_as": "persona"}
""".replace('{', '{{').replace('}', '}}')
        
        db_plan_prompt = ChatPromptTemplate.from_messages([
            ("system", textwrap.dedent(f"""
                당신은 데이터베이스 쿼리 작성자입니다.
                
                # 요청 정보
                - 기관명: {org_name}
                - 보고서 주제: {report_topic}
                
                # 데이터베이스 스키마
                {escaped_schema}
                
                # 쿼리 예시
                {query_examples}
                
                # 주의사항
                - cri_ym(기준년월)은 정수형. 예: 202501
                - cutr_facl_id(시설ID)는 정수형.
                - 이전 쿼리 결과 참조: "{{{{save_as}}}}.{{{{column}}}}" 형식
                
                # 지시
                1. 먼저 왜 이 쿼리들이 필요한지 간단히 설명하라 (1-2문장).
                2. 그 다음 execute_data_queries를 호출하여 queries 배열에 쿼리를 담아 전달하라.
            """).strip()),
            ("human", f"'{org_name}' 보고서 작성에 필요한 모든 데이터를 DB에서 가져오기 위한 쿼리를 작성하고 execute_data_queries를 호출하라.")
        ])
        
        db_tools = [execute_data_queries]
        db_chain = db_plan_prompt | llm.bind_tools(db_tools)
        
        try:
            db_response = db_chain.invoke({})
            logger.info(f"[SEARCH_AGENT] [단계1] DB 계획 LLM 응답 완료")
            logger.info(f"[SEARCH_AGENT] [단계1] 응답 타입: {type(db_response)}")
            if hasattr(db_response, "content"):
                logger.info(f"[SEARCH_AGENT] [단계1] content: {str(db_response.content)[:300]}")
            if hasattr(db_response, "tool_calls"):
                logger.info(f"[SEARCH_AGENT] [단계1] tool_calls 개수: {len(db_response.tool_calls) if db_response.tool_calls else 0}")
                if db_response.tool_calls:
                    for i, tc in enumerate(db_response.tool_calls):
                        logger.info(f"[SEARCH_AGENT] [단계1] tool_call[{i}]: name={tc.get('name')}, args_keys={list(tc.get('args', {}).keys())}")
                        logger.info(f"[SEARCH_AGENT] [단계1] tool_call[{i}] args: {str(tc.get('args', {}))[:500]}")
        except Exception as e:
            logger.error(f"[SEARCH_AGENT] [단계1] DB 계획 LLM 실패: {e}")
            db_response = None
        
        # === 설정 기반 쿼리 번들 로드 ===
        default_queries, bundle_stats, block_configs = get_all_for_org(org_name)
        logger.info(f"[SEARCH_AGENT] [단계1] 번들 로드: {len(default_queries)}개 쿼리, 통계: {bundle_stats}")
        
        # 통계 이름 매핑 (번들 설정 → query_executor 형식)
        stats_name_map = {"review": "review_stats", "demographics": "demographics_stats"}
        default_stats = [stats_name_map.get(s, f"{s}_stats") for s in bundle_stats]
        
        llm_queries: List[Dict[str, Any]] = []
        llm_stats: List[str] = []
        db_plan_reasoning: str = ""  # LLM의 DB 계획 설명
        
        # LLM 응답에서 텍스트 설명 추출
        if db_response and hasattr(db_response, "content") and db_response.content:
            db_plan_reasoning = db_response.content.strip()
            if db_plan_reasoning:
                logger.info(f"[SEARCH_AGENT] [단계1] DB 계획 설명: {db_plan_reasoning[:200]}...")
        
        if db_response and hasattr(db_response, "tool_calls") and db_response.tool_calls:
            for call in db_response.tool_calls:
                if call.get("name") == "execute_data_queries":
                    args = call.get("args", {})
                    if args.get("queries"):
                        llm_queries = args["queries"]
                        logger.info(f"[SEARCH_AGENT] [단계1] LLM 쿼리 추출: {len(llm_queries)}개")
                    if args.get("calculate_stats"):
                        llm_stats = args["calculate_stats"]
                        logger.info(f"[SEARCH_AGENT] [단계1] LLM 통계 추출: {llm_stats}")
                    break
        
        existing_save_as = {q["save_as"] for q in default_queries if "save_as" in q}
        merged_queries = list(default_queries)
        
        for q in llm_queries:
            if q.get("save_as") not in existing_save_as:
                merged_queries.append(q)
                existing_save_as.add(q.get("save_as"))
                logger.info(f"[SEARCH_AGENT] [단계1] LLM 쿼리 추가: {q.get('save_as')}")
        
        merged_stats = list(default_stats)
        for s in llm_stats:
            if s not in merged_stats:
                merged_stats.append(s)
        
        db_plan = {
            "queries": merged_queries,
            "calculate_stats": merged_stats
        }
        
        logger.info(f"[SEARCH_AGENT] [단계1] 최종 DB 계획: queries={len(merged_queries)}개, stats={merged_stats}")

        # 단계 2: API 선택
        logger.info(f"[SEARCH_AGENT] [단계2] API 선택 LLM 호출")
        
        api_tools = [
            toolkit.search_exhibition_info_api,
            toolkit.search_museum_collection_api,
            toolkit.search_performance_info_api,
        ]
        
        api_plan_prompt = ChatPromptTemplate.from_messages([
            ("system", textwrap.dedent(f"""
                당신은 문화시설 API 선택 전문가입니다.
            
            # 요청 정보
                - 기관명: {org_name}
                - 보고서 주제: {report_topic}
                
                # 사용 가능한 API
                - search_exhibition_info_api: 전시 정보 검색 (미술관, 박물관, 갤러리용)
                - search_museum_collection_api: 소장품 검색 (박물관 전용)
                - search_performance_info_api: 공연 정보 검색 (공연장, 콘서트홀용)
                
                # 지시사항
                1. 먼저 왜 이 API를 선택했는지 간단히 설명하세요 (1-2문장).
                2. 기관 유형에 맞는 API를 선택하여 호출하세요.
                   - 미술관/박물관/갤러리: search_exhibition_info_api
                   - 박물관 소장품: search_museum_collection_api  
                   - 공연장/콘서트홀: search_performance_info_api
                
                keyword 파라미터에 기관명을 넣으세요.
            """).strip()),
            ("human", f"'{org_name}'에 적합한 API를 선택하여 호출하세요.")
        ])
        
        api_chain = api_plan_prompt | llm.bind_tools(api_tools)
        
        try:
            api_response = api_chain.invoke({})
            logger.info(f"[SEARCH_AGENT] [단계2] API 선택 LLM 응답 완료")
        except Exception as e:
            logger.error(f"[SEARCH_AGENT] [단계2] API 선택 LLM 실패: {e}")
            api_response = None
        
        api_calls: List[Dict[str, Any]] = []
        api_plan_reasoning: str = ""  # LLM의 API 선택 이유
        
        # LLM 응답에서 텍스트 설명 추출
        if api_response and hasattr(api_response, "content") and api_response.content:
            api_plan_reasoning = api_response.content.strip()
            if api_plan_reasoning:
                logger.info(f"[SEARCH_AGENT] [단계2] API 선택 이유: {api_plan_reasoning[:200]}...")
        
        if api_response and hasattr(api_response, "tool_calls") and api_response.tool_calls:
            for call in api_response.tool_calls:
                api_calls.append({
                    "name": call.get("name"),
                    "args": call.get("args", {}),
                    "reasoning": api_plan_reasoning  # 각 API 호출에 이유 저장
                })
            logger.info(f"[SEARCH_AGENT] [단계2] API 계획: {[c['name'] for c in api_calls]}")
        else:
            logger.warning(f"[SEARCH_AGENT] [단계2] API 선택 없음")

        # 단계 3: DB 쿼리 실행
        logger.info(f"[SEARCH_AGENT] [단계3] DB 계획 실행")
        
        try:
            db_result = execute_data_queries.invoke(db_plan)
            logger.info(f"[SEARCH_AGENT] [단계3] DB 실행 완료: {list(db_result.keys()) if isinstance(db_result, dict) else type(db_result)}")
            
            if isinstance(db_result, dict):
                skip_keys = {"success", "errors", "stats"}
                for key, value in db_result.items():
                    if key in skip_keys:
                        continue
                    if isinstance(value, dict) and value.get("count", 0) > 0:
                        research_payload.append({
                            "tool": f"execute_data_queries.{key}",
                            "count": value["count"],
                            "sample": value.get("sample", []),
                            "data": value.get("sample", []),  # Analyse Agent용
                            "reasoning": db_plan_reasoning  # 수집 이유/계획 설명
                        })
                        logger.info(f"[SEARCH_AGENT] [단계3] {key}: {value['count']}개 추가")
                
                stats = db_result.get("stats")
                if stats:
                    research_payload.append({
                        "tool": "calculated_stats",
                        "stats": stats,
                        "block_configs": block_configs,  # 번들별 블록 설정 전달
                        "reasoning": "리뷰 평점 분포와 방문자 인구통계를 분석하기 위해 자동 계산된 통계입니다."
                    })
                    logger.info(f"[SEARCH_AGENT] [단계3] 통계 추가: {list(stats.keys())}, 블록 설정: {list(block_configs.keys())}")
                
                if db_result.get("errors"):
                    logger.error(f"[SEARCH_AGENT] [단계3] DB 오류: {db_result['errors']}")
                    
        except Exception as e:
            logger.error(f"[SEARCH_AGENT] [단계3] DB 실행 실패: {e}")

        # 단계 4: API 호출 실행
        logger.info(f"[SEARCH_AGENT] [단계4] API 실행 ({len(api_calls)}개)")
        
        api_tool_map = {t.name: t for t in api_tools}
        
        for api_call in api_calls:
            tool_name = api_call.get("name")
            tool_args = api_call.get("args", {})
            
            tool_fn = api_tool_map.get(tool_name)
            if not tool_fn:
                logger.warning(f"[SEARCH_AGENT] [단계4] API 도구 없음: {tool_name}")
                continue

            logger.info(f"[SEARCH_AGENT] [단계4] API 호출: {tool_name}")
            try:
                tool_result = tool_fn.invoke(tool_args)
                
                if isinstance(tool_result, dict):
                    data = tool_result.get("data", [])
                    if data:
                        if current_date and tool_name in ["search_exhibition_info_api", "search_performance_info_api"]:
                            filtered = _filter_by_current_date(data, current_date)
                            if len(filtered) < len(data):
                                logger.info(f"[SEARCH_AGENT] [단계4] 날짜 필터링: {len(data)} -> {len(filtered)}")
                                data = filtered
                        
                        if not latest_performance_image:
                            img = _extract_latest_image(data)
                            if img:
                                latest_performance_image = img
                                logger.info(f"[SEARCH_AGENT] [단계4] 이미지 추출 완료")
                        
                        research_payload.append({
                            "tool": tool_name,
                            "count": len(data),
                            "sample": data[:5],
                            "data": data,
                            "reasoning": api_call.get("reasoning", "")  # API 호출 이유
                        })
                        logger.info(f"[SEARCH_AGENT] [단계4] {tool_name}: {len(data)}개 결과")
                        
            except Exception as e:
                logger.error(f"[SEARCH_AGENT] [단계4] API 실행 실패: {tool_name} - {e}")

        # 단계 5: Google API 번들 실행
        logger.info(f"[SEARCH_AGENT] [단계5] Google API 번들 실행")
        
        try:
            # DB 결과에서 좌표 추출
            lat, lng, address = None, None, ""
            
            # research_payload에서 좌표 찾기
            for item in research_payload:
                tool_name = item.get("tool", "")
                data = item.get("data", []) or item.get("sample", [])
                
                if not data or not isinstance(data, list):
                    continue
                
                first_record = data[0] if data else {}
                
                # LG U+ 데이터에서 좌표 (cutr_facl_xcrd, cutr_facl_ycrd)
                if "lgu_facility" in tool_name or "demographics" in tool_name:
                    if first_record.get("cutr_facl_xcrd") and first_record.get("cutr_facl_ycrd"):
                        lng = float(first_record["cutr_facl_xcrd"])
                        lat = float(first_record["cutr_facl_ycrd"])
                        address = first_record.get("cutr_facl_addr", "")
                        logger.info(f"[SEARCH_AGENT] [단계5] LGU+ 좌표 발견: ({lat}, {lng})")
                        break
                
                # SNS버즈 데이터에서 좌표 (slta_xcrd, slta_ycrd)
                if "facility" in tool_name:
                    if first_record.get("slta_xcrd") and first_record.get("slta_ycrd"):
                        lng = float(first_record["slta_xcrd"])
                        lat = float(first_record["slta_ycrd"])
                        address = first_record.get("slta_addr", "")
                        logger.info(f"[SEARCH_AGENT] [단계5] SNS버즈 좌표 발견: ({lat}, {lng})")
                        break
            
            # 좌표가 있으면 Google API 번들 실행
            if lat and lng:
                # 컨텍스트 구성
                google_context = {
                    "org": org_name,
                    "lat": lat,
                    "lng": lng,
                    "address": address
                }
                
                # 기관별 preset으로 번들 실행
                preset = api_bundle_loader.get_preset_for_org(org_name)
                bundle_names = api_bundle_loader.get_bundles_for_preset(preset)
                
                logger.info(f"[SEARCH_AGENT] [단계5] preset: {preset}, 번들: {bundle_names}")
                
                for bundle_name in bundle_names:
                    try:
                        api_result, block_config = api_bundle_loader.execute_api_bundle(
                            bundle_name, google_context
                        )
                        
                        if api_result.get("success"):
                            research_payload.append({
                                "tool": f"google_api.{bundle_name}",
                                "data": api_result,
                                "block_config": block_config,
                                "reasoning": f"Google API '{bundle_name}' 번들 실행 결과"
                            })
                            logger.info(f"[SEARCH_AGENT] [단계5] {bundle_name} 성공")
                        else:
                            logger.warning(f"[SEARCH_AGENT] [단계5] {bundle_name} 실패: {api_result.get('error')}")
                    
                    except Exception as bundle_error:
                        logger.error(f"[SEARCH_AGENT] [단계5] {bundle_name} 오류: {bundle_error}")
            else:
                logger.info(f"[SEARCH_AGENT] [단계5] 좌표 없음, Google API 스킵")
        
        except Exception as e:
            logger.error(f"[SEARCH_AGENT] [단계5] Google API 실행 오류: {e}")

        # 결과 정리
        logger.info(f"[SEARCH_AGENT] ====== 완료 ======")
        logger.info(f"[SEARCH_AGENT] 수집된 데이터: {len(research_payload)}개")
        for item in research_payload:
            tool = item.get("tool", "unknown")
            count = item.get("count", 0)
            logger.info(f"[SEARCH_AGENT]   - {tool}: {count}개")

        return {
            "messages": messages,
            "research_payload": research_payload,
            "latest_performance_image": latest_performance_image,
        }

    return search_agent_node
