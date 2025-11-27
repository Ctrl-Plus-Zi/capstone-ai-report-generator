from langchain.tools import tool
from typing import Annotated, Optional, Dict, Any, List
import json
import os

from app.db.context import get_capstone_db_context
from app.agents.db_query_tool import (
    query_cultural_facility_data,
    query_with_filters,
    query_with_range_and_search,
    get_aggregate_statistics
)


def load_db_configs():
    """DB 테이블 설정 정보를 로드합니다."""
    config_path = os.path.join(os.path.dirname(__file__), "db_configs.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_db_schema_info() -> str:
    """에이전트에게 제공할 DB 스키마 정보를 문자열로 반환 (간결한 형식)"""
    configs = load_db_configs()
    
    lines = ["# DB 테이블 스키마"]
    
    for table_name, table_info in configs.items():
        lines.append(f"\n## {table_name}")
        lines.append(f"{table_info['desc']}")
        lines.append(f"검색필드: {', '.join(table_info['search'])}")
        lines.append("컬럼:")
        
        for col_name, col_desc in table_info['cols'].items():
            lines.append(f"  {col_name}: {col_desc}")
    
    return "\n".join(lines)


@tool
def search_database(
    table_name: Annotated[str, "조회할 테이블명"],
    search_column: Annotated[Optional[str], "검색할 컬럼명"] = None,
    search_value: Annotated[Optional[str], "검색값 (부분 일치로 검색됨)"] = None,
    limit: Annotated[int, "최대 조회 개수 (기본 50)"] = 50
) -> str:
    """
    데이터베이스에서 데이터를 검색합니다. LIKE 검색으로 부분 일치하는 데이터를 찾습니다.
    
    사용 예시:
    - search_database("cultural_facilities", "name", "박물관")
      → name 컬럼에 '박물관'이 포함된 모든 행
    - search_database("facility_events", "event_type", "전시")
      → event_type에 '전시'가 포함된 이벤트
    - search_database("users", "email", "gmail.com")
      → 이메일에 'gmail.com'이 포함된 사용자
    
    Returns:
        JSON 형태의 조회 결과
    """
    with get_capstone_db_context() as db:
        result = query_cultural_facility_data(
            table_name=table_name,
            search_column=search_column,
            search_value=search_value,
            limit=limit,
            db=db
        )
        return result


@tool
def filter_database(
    table_name: Annotated[str, "조회할 테이블명"],
    filters: Annotated[str, "필터 조건 (JSON 문자열 형식, 예: '{\"category\": \"박물관\", \"year\": 2024}')"],
    order_by: Annotated[Optional[str], "정렬 기준 컬럼명"] = None,
    limit: Annotated[int, "최대 조회 개수"] = 50
) -> str:
    """
    여러 조건으로 데이터를 필터링하여 조회합니다. 정확히 일치하는 조건으로 필터링합니다.
    
    사용 예시:
    - filter_database("cultural_facilities", '{"category": "박물관"}', "created_at", 20)
      → category가 정확히 "박물관"인 행을 created_at 순으로 20개
    - filter_database("facility_events", '{"status": "진행중", "event_type": "전시"}', None, 30)
      → status가 "진행중"이고 event_type이 "전시"인 행 30개
    - filter_database("users", '{"role": "admin", "is_active": true}')
      → role이 "admin"이고 is_active가 true인 사용자
    
    Returns:
        JSON 형태의 필터링된 결과
    """
    try:
        filter_dict = json.loads(filters)
    except json.JSONDecodeError:
        return json.dumps({"error": "filters는 유효한 JSON 문자열이어야 합니다."}, ensure_ascii=False)
    
    with get_capstone_db_context() as db:
        result = query_with_filters(
            table_name=table_name,
            filters=filter_dict,
            order_by=order_by,
            limit=limit,
            db=db
        )
        return result


@tool
def query_with_range_filter(
    table_name: Annotated[str, "조회할 테이블명"],
    search_column: Annotated[Optional[str], "LIKE 검색할 컬럼명"] = None,
    search_value: Annotated[Optional[str], "LIKE 검색값"] = None,
    range_column: Annotated[Optional[str], "범위 조건 컬럼명 (예: year, created_at, date)"] = None,
    range_start: Annotated[Optional[Any], "범위 시작값"] = None,
    range_end: Annotated[Optional[Any], "범위 종료값 (생략 시 range_start와 동일)"] = None,
    order_by: Annotated[Optional[str], "정렬 기준 컬럼명"] = None,
    limit: Annotated[int, "최대 조회 개수 (기본 100)"] = 100
) -> str:
    """
    범위 조건과 검색 조건을 동시에 적용하여 데이터를 조회합니다.
    날짜/연도 범위, 숫자 범위 등 모든 범위 조건에 사용 가능합니다.
    
    사용 예시:
    - query_with_range_filter("facility_statistics", "facility_name", "국립중앙박물관", "year", 2023, 2024)
      → facility_statistics 테이블에서 국립중앙박물관의 2023~2024년 데이터
    - query_with_range_filter("cultural_facilities", None, None, "created_at", "2023-01-01", "2023-12-31")
      → 2023년에 등록된 모든 시설
    - query_with_range_filter("facility_events", "event_type", "전시", "year", 2024, None)
      → 2024년 전시 이벤트
    
    Returns:
        JSON 형태의 조회 결과
    """
    with get_capstone_db_context() as db:
        result = query_with_range_and_search(
            table_name=table_name,
            search_column=search_column,
            search_value=search_value,
            range_column=range_column,
            range_start=range_start,
            range_end=range_end,
            order_by=order_by,
            limit=limit,
            db=db
        )
        return result


@tool
def get_aggregated_statistics(
    table_name: Annotated[str, "테이블명"],
    group_by: Annotated[str, "그룹화 기준 컬럼 (예: category, event_type, status)"],
    aggregate_column: Annotated[str, "집계할 컬럼 (예: id, visitor_count, price)"] = "id",
    aggregate_function: Annotated[str, "집계 함수 (count, sum, avg, max, min)"] = "count"
) -> str:
    """
    데이터를 그룹화하여 집계 통계를 조회합니다. GROUP BY + 집계 함수를 사용합니다.
    
    사용 예시:
    - get_aggregated_statistics("cultural_facilities", "category", "id", "count")
      → 카테고리별 시설 개수
    - get_aggregated_statistics("facility_statistics", "facility_name", "visitor_count", "sum")
      → 시설별 총 방문자 수
    - get_aggregated_statistics("orders", "product_id", "amount", "sum")
      → 제품별 총 판매 금액
    - get_aggregated_statistics("students", "grade", "score", "avg")
      → 학년별 평균 점수
    
    Returns:
        JSON 형태의 집계 결과 (내림차순으로 정렬됨)
    """
    with get_capstone_db_context() as db:
        result = get_aggregate_statistics(
            table_name=table_name,
            group_by=group_by,
            aggregate_column=aggregate_column,
            aggregate_function=aggregate_function,
            db=db
        )
        return result


@tool
def get_database_schema_info() -> str:
    """
    사용 가능한 데이터베이스 테이블과 컬럼 정보를 조회합니다.
    어떤 데이터를 조회할 수 있는지 확인할 때 사용하세요.
    
    Returns:
        데이터베이스 스키마 정보 (테이블명, 컬럼명, 설명)
    """
    return get_db_schema_info()


db_tools = [
    search_database,
    filter_database,
    query_with_range_filter,
    get_aggregated_statistics,
    get_database_schema_info
]


DB_SCHEMA_CONTEXT = get_db_schema_info()

