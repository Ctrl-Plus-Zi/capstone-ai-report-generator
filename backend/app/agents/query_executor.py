"""
Query Executor - DB 쿼리 순차 실행 및 통계 계산

capstone DB에서 팀원 데이터를 조회합니다.
"""

import json
import logging
import re
from typing import List, Dict, Any, Annotated, Optional
from langchain_core.tools import tool

from app.db.context import get_capstone_db_context
from app.agents.db_query_tool import DBQueryTool

logger = logging.getLogger("uvicorn.error")


def _resolve_reference(value: Any, context: Dict[str, Any]) -> Any:
    """참조 문자열을 실제 값으로 치환 (예: {facility.slta_cd} -> SLTA062)"""
    if not isinstance(value, str):
        return value
    
    pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\}'
    
    def replacer(match):
        path = match.group(1)
        parts = path.split('.')
        
        result = context
        for part in parts:
            if isinstance(result, dict) and part in result:
                result = result[part]
            elif isinstance(result, list) and len(result) > 0:
                result = result[0].get(part) if isinstance(result[0], dict) else None
            else:
                return match.group(0)
        
        return str(result) if result is not None else match.group(0)
    
    return re.sub(pattern, replacer, value)


def _resolve_params(params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """params 내 모든 참조 해결"""
    resolved = {}
    for key, value in params.items():
        if isinstance(value, str):
            resolved_val = _resolve_reference(value, context)
            if isinstance(resolved_val, str) and resolved_val.isdigit():
                resolved[key] = int(resolved_val)
            else:
                resolved[key] = resolved_val
        elif isinstance(value, dict):
            resolved[key] = _resolve_params(value, context)
        else:
            resolved[key] = value
    return resolved


def _calculate_review_stats(reviews: List[Dict]) -> Dict[str, Any]:
    """리뷰 평점 분포 통계 계산"""
    if not reviews:
        return {
            "total_reviews": 0,
            "average_rating": 0,
            "rating_distribution": {},
            "summary": "리뷰 데이터가 없습니다."
        }
    rating_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    total = 0
    rating_sum = 0
    
    for review in reviews:
        rating = review.get("sns_content_rating")
        if rating is not None:
            try:
                rating_int = int(round(float(rating)))
                if 1 <= rating_int <= 5:
                    rating_counts[rating_int] += 1
                    total += 1
                    rating_sum += float(rating)
            except (ValueError, TypeError):
                continue
    
    avg_rating = round(rating_sum / total, 2) if total > 0 else 0
    
    distribution = {}
    for rating, count in rating_counts.items():
        pct = round(count / total * 100, 1) if total > 0 else 0
        distribution[f"{rating}점"] = {"count": count, "percent": pct}
    
    max_rating = max(rating_counts, key=rating_counts.get)
    max_pct = distribution[f"{max_rating}점"]["percent"]
    
    summary = f"평균 {avg_rating}점 (총 {total}개 리뷰). {max_rating}점 리뷰가 {max_pct}%로 가장 많습니다."
    
    return {
        "total_reviews": total,
        "average_rating": avg_rating,
        "rating_distribution": distribution,
        "summary": summary
    }


def _calculate_demographics_stats(demographics: List[Dict]) -> Dict[str, Any]:
    """인구통계 연령/성별 분포 통계 계산 (LG U+, 삼성카드, 페르소나 형식 지원)"""
    if not demographics:
        return {
            "has_data": False,
            "summary": "인구통계 데이터가 없습니다."
        }
    
    data = demographics[0]
    keys = list(data.keys())
    logger.info(f"[QUERY_EXECUTOR] demographics 키: {keys[:15]}")
    
    age_stats = {}
    gender_stats = {"male": 0, "female": 0}
    
    # LG U+ lguplus_dpg_api_tot 형식: m_20, f_20, ...
    if "m_20" in data:
        logger.info(f"[QUERY_EXECUTOR] LG U+ API 형식 감지 (m_20, f_20...)")
        age_groups = ["20", "30", "40", "50", "60", "70"]
        for age in age_groups:
            male_val = float(data.get(f"m_{age}", 0) or 0)
            female_val = float(data.get(f"f_{age}", 0) or 0)
            age_stats[f"{age}대"] = round(male_val + female_val, 1)
            gender_stats["male"] += male_val
            gender_stats["female"] += female_val
    
    # 삼성카드 mrcno_demographics 형식: mrcno_pct_20_male, ...
    elif "mrcno_pct_20_male" in data:
        logger.info(f"[QUERY_EXECUTOR] 삼성카드 형식 감지 (mrcno_pct_...)")
        age_groups = ["20", "30", "40", "50", "60", "70"]
        for age in age_groups:
            male_val = float(data.get(f"mrcno_pct_{age}_male", 0) or 0) * 100
            female_val = float(data.get(f"mrcno_pct_{age}_female", 0) or 0) * 100
            age_stats[f"{age}대"] = round(male_val + female_val, 1)
            gender_stats["male"] += male_val
            gender_stats["female"] += female_val
    
    # 페르소나 형식: persona_pct_20_male, ...
    elif "persona_pct_20_male" in data:
        logger.info(f"[QUERY_EXECUTOR] 페르소나 형식 감지 (persona_pct_...)")
        age_groups = ["20", "30", "40", "50", "60", "70"]
        for age in age_groups:
            male_val = float(data.get(f"persona_pct_{age}_male", 0) or 0) * 100
            female_val = float(data.get(f"persona_pct_{age}_female", 0) or 0) * 100
            age_stats[f"{age}대"] = round(male_val + female_val, 1)
            gender_stats["male"] += male_val
            gender_stats["female"] += female_val
    
    else:
        logger.warning(f"[QUERY_EXECUTOR] 인식되지 않는 demographics 형식")
        return {
            "has_data": False,
            "summary": "인구통계 데이터 형식을 인식할 수 없습니다."
        }
    
    if not age_stats or all(v == 0 for v in age_stats.values()):
        return {
            "has_data": False,
            "summary": "인구통계 데이터가 비어있습니다."
        }
    
    max_age = max(age_stats, key=age_stats.get)
    max_age_pct = age_stats[max_age]
    
    male_pct = round(gender_stats["male"], 1)
    female_pct = round(gender_stats["female"], 1)
    
    if female_pct > male_pct:
        gender_summary = f"여성 {female_pct}% > 남성 {male_pct}%"
    else:
        gender_summary = f"남성 {male_pct}% > 여성 {female_pct}%"
    
    summary = f"주요 방문층: {max_age} ({max_age_pct}%). {gender_summary}"
    
    return {
        "has_data": True,
        "age_distribution": age_stats,
        "gender_distribution": {"남성": male_pct, "여성": female_pct},
        "summary": summary
    }


@tool
def execute_data_queries(
    queries: Annotated[List[Dict[str, Any]], """
[필수] 실행할 쿼리 배열. 반드시 제공해야 함.

각 쿼리 형식:
{
  "action": "search" | "filter" | "range_filter" | "aggregate",
  "table": "테이블명",
  "params": { ... },
  "save_as": "결과저장키"
}

## action별 params 예시:

### search (LIKE 검색):
{"search_column": "slta_nm", "search_value": "예술의전당", "limit": 10}

### filter (정확한 값 필터):
{"filters": {"slta_cd": "SLTA018"}, "limit": 50}
{"filters": {"cutr_facl_id": 7232880, "cri_ym": 202501}, "limit": 12}

### range_filter (범위 조건):
{"column": "cri_ym", "min_value": 202401, "max_value": 202412, "filters": {"cutr_facl_id": 7232880}}

### aggregate (집계):
{"group_by": "slta_cd", "aggregate_column": "sns_content_rating", "aggregate_function": "avg"}

## 이전 결과 참조:
params에서 "{save_as.column}" 형식으로 이전 쿼리 결과 참조 가능.
예: {"filters": {"slta_cd": "{facility.slta_cd}"}}
"""],
    calculate_stats: Annotated[Optional[List[str]], """
[선택] 자동 통계 계산. 허용값:
- "review_stats": 리뷰 평점 분포 (save_as="reviews" 필요)
- "demographics_stats": 연령/성별 분포 (save_as="demographics" 필요)
"""] = None
) -> Dict[str, Any]:
    """
    DB 쿼리를 순서대로 실행하고 통계를 계산합니다.
    
    ## 사용 예시
    
    queries=[
      {"action": "search", "table": "sns_buzz_master_tbl", 
       "params": {"search_column": "slta_nm", "search_value": "예술의전당"}, 
       "save_as": "facility"},
      {"action": "filter", "table": "persona_metrics", 
       "params": {"filters": {"cutr_facl_id": "{facility.cutr_facl_id}", "cri_ym": 202501}}, 
       "save_as": "persona"}
    ],
    calculate_stats=["review_stats", "demographics_stats"]
    """
    results = {}
    errors = []
    
    with get_capstone_db_context() as db:
        query_tool = DBQueryTool(db)
        
        for i, query in enumerate(queries):
            action = query.get("action", "search")
            table = query.get("table", "")
            params = query.get("params", {})
            save_as = query.get("save_as", f"result_{i}")
            resolved_params = _resolve_params(params, results)
            
            logger.info(f"[QUERY_EXECUTOR] {i+1}. {action} on {table}, params={resolved_params}")
            
            try:
                if action == "search":
                    data = query_tool.query(
                        table_name=table,
                        search_column=resolved_params.get("search_column"),
                        search_value=resolved_params.get("search_value"),
                        limit=resolved_params.get("limit", 10)
                    )
                
                elif action == "filter":
                    filters = resolved_params.get("filters", {})
                    if isinstance(filters, str):
                        filters = json.loads(filters)
                    
                    data = query_tool.query(
                        table_name=table,
                        filters=filters,
                        limit=resolved_params.get("limit", 50)
                    )
                
                elif action == "aggregate":
                    data = query_tool.get_aggregated_statistics(
                        table_name=table,
                        group_by=resolved_params.get("group_by"),
                        aggregate_column=resolved_params.get("aggregate_column"),
                        aggregate_function=resolved_params.get("aggregate_function", "count"),
                        filters=resolved_params.get("filters")
                    )
                
                else:
                    data = [{"error": f"Unknown action: {action}"}]
                
                results[save_as] = data
                logger.info(f"[QUERY_EXECUTOR] {save_as}: {len(data) if isinstance(data, list) else 1}개 결과")
                
            except Exception as e:
                error_msg = f"{table} 조회 오류: {str(e)}"
                errors.append(error_msg)
                results[save_as] = []
                logger.warning(f"[QUERY_EXECUTOR] {error_msg}")
    
    stats = {}
    if calculate_stats:
        if "review_stats" in calculate_stats and "reviews" in results:
            stats["review_stats"] = _calculate_review_stats(results["reviews"])
            logger.info(f"[QUERY_EXECUTOR] 리뷰 통계 계산 완료: {stats['review_stats']['summary']}")
        
        if "demographics_stats" in calculate_stats and "demographics" in results:
            stats["demographics_stats"] = _calculate_demographics_stats(results["demographics"])
            logger.info(f"[QUERY_EXECUTOR] 인구통계 분석 완료: {stats['demographics_stats']['summary']}")
    
    output = {
        "success": len(errors) == 0,
        "errors": errors if errors else None,
        "stats": stats if stats else None,
    }
    
    for key, data in results.items():
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0] if isinstance(data[0], dict) else {}
            output[key] = {
                "count": len(data),
                "sample": data[:3],  # 샘플 3개만
                "keys": list(first_item.keys()) if first_item else []
            }
        else:
            output[key] = {"count": 0, "sample": [], "keys": []}
    
    return output


# 도구 리스트 (search_agent에서 사용)
query_executor_tools = [execute_data_queries]

