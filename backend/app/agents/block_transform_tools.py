"""DB 데이터를 차트/테이블 블록으로 변환하는 도구

이 모듈은 research_payload에서 추출한 원본 데이터를
시각화용 블록으로 자동 변환하는 LangChain 도구들을 제공합니다.
"""

from typing import List, Dict, Any, Annotated
from langchain_core.tools import tool


@tool
def transform_demographics_to_age_chart(
    demographics_data: Annotated[List[Dict[str, Any]], "mrcno_demographics 또는 persona_metrics 테이블에서 조회한 데이터 리스트"]
) -> dict:
    """인구통계 데이터를 연령대별 방문자 분포 도넛 차트로 변환합니다.
    
    입력 데이터 예시 (mrcno_demographics):
    [{"mrcno_pct_20_male": 10.5, "mrcno_pct_20_female": 12.3, ...}]
    
    또는 (persona_metrics):
    [{"persona_pct_20_male": 10.5, "persona_pct_20_female": 12.3, ...}]
    
    Returns:
        연령대별 분포 차트 블록 (doughnut)
    """
    if not demographics_data:
        return {
            "type": "chart",
            "chartType": "doughnut",
            "title": "연령대별 방문자 분포",
            "data": {"labels": [], "values": []},
            "description": "데이터가 없습니다."
        }
    
    # 첫 번째 레코드 사용 (또는 평균 계산)
    data = demographics_data[0] if len(demographics_data) == 1 else _average_demographics(demographics_data)
    
    # 컬럼 접두사 자동 감지 (mrcno_pct_ 또는 persona_pct_)
    prefix = "mrcno_pct_" if "mrcno_pct_20_male" in data else "persona_pct_"
    
    # 연령대별 합계 계산 (남+여)
    age_groups = ["20", "30", "40", "50", "60", "70"]
    labels = ["20대", "30대", "40대", "50대", "60대", "70대 이상"]
    values = []
    
    for age in age_groups:
        male_key = f"{prefix}{age}_male"
        female_key = f"{prefix}{age}_female"
        male_val = float(data.get(male_key, 0) or 0)
        female_val = float(data.get(female_key, 0) or 0)
        values.append(round(male_val + female_val, 1))
    
    # 가장 높은 연령대 찾기
    max_idx = values.index(max(values)) if values else 0
    max_age = labels[max_idx]
    max_val = values[max_idx]
    
    return {
        "type": "chart",
        "chartType": "doughnut",
        "title": "연령대별 방문자 분포",
        "data": {"labels": labels, "values": values},
        "description": f"{max_age} 방문자가 {max_val}%로 가장 높은 비중을 차지합니다."
    }


@tool
def transform_demographics_to_gender_chart(
    demographics_data: Annotated[List[Dict[str, Any]], "mrcno_demographics 또는 persona_metrics 테이블에서 조회한 데이터 리스트"]
) -> dict:
    """인구통계 데이터를 성별 방문자 분포 도넛 차트로 변환합니다.
    
    Returns:
        성별 분포 차트 블록 (doughnut)
    """
    if not demographics_data:
        return {
            "type": "chart",
            "chartType": "doughnut",
            "title": "성별 방문자 분포",
            "data": {"labels": ["남성", "여성"], "values": [50, 50]},
            "description": "데이터가 없습니다."
        }
    
    # 첫 번째 레코드 사용 (또는 평균 계산)
    data = demographics_data[0] if len(demographics_data) == 1 else _average_demographics(demographics_data)
    
    # 컬럼 접두사 자동 감지
    prefix = "mrcno_pct_" if "mrcno_pct_20_male" in data else "persona_pct_"
    
    # 성별 합계 계산
    age_groups = ["20", "30", "40", "50", "60", "70"]
    male_total = 0
    female_total = 0
    
    for age in age_groups:
        male_total += float(data.get(f"{prefix}{age}_male", 0) or 0)
        female_total += float(data.get(f"{prefix}{age}_female", 0) or 0)
    
    male_pct = round(male_total, 1)
    female_pct = round(female_total, 1)
    
    # 더 높은 성별 확인
    if female_pct > male_pct:
        desc = f"여성 방문자가 {female_pct}%로 남성({male_pct}%)보다 높습니다."
    elif male_pct > female_pct:
        desc = f"남성 방문자가 {male_pct}%로 여성({female_pct}%)보다 높습니다."
    else:
        desc = f"남성과 여성 방문자 비율이 각각 {male_pct}%로 동일합니다."
    
    return {
        "type": "chart",
        "chartType": "doughnut",
        "title": "성별 방문자 분포",
        "data": {"labels": ["남성", "여성"], "values": [male_pct, female_pct]},
        "description": desc
    }


@tool
def transform_reviews_to_rating_chart(
    review_data: Annotated[List[Dict[str, Any]], "sns_buzz_extract_contents 테이블에서 조회한 리뷰 데이터 리스트 (sns_content_rating 포함)"]
) -> dict:
    """구글맵 리뷰 데이터를 평점 분포 막대 차트로 변환합니다.
    
    입력: [{"sns_content_rating": 5.0, ...}, {"sns_content_rating": 4.0, ...}, ...]
    
    Returns:
        평점 분포 차트 블록 (bar)
    """
    if not review_data:
        return {
            "type": "chart",
            "chartType": "bar",
            "title": "리뷰 평점 분포",
            "data": {"labels": ["5점", "4점", "3점", "2점", "1점"], "values": [0, 0, 0, 0, 0]},
            "description": "리뷰 데이터가 없습니다."
        }
    
    # 평점별 카운트
    rating_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    total = 0
    rating_sum = 0
    
    for review in review_data:
        rating = review.get("sns_content_rating")
        if rating is not None:
            rating_int = int(round(float(rating)))
            if 1 <= rating_int <= 5:
                rating_counts[rating_int] += 1
                total += 1
                rating_sum += float(rating)
    
    labels = ["5점", "4점", "3점", "2점", "1점"]
    values = [rating_counts[5], rating_counts[4], rating_counts[3], rating_counts[2], rating_counts[1]]
    
    # 평균 평점 계산
    avg_rating = round(rating_sum / total, 1) if total > 0 else 0
    
    # 가장 많은 평점 찾기
    max_rating = max(rating_counts, key=rating_counts.get)
    max_count = rating_counts[max_rating]
    max_pct = round(max_count / total * 100, 1) if total > 0 else 0
    
    return {
        "type": "chart",
        "chartType": "bar",
        "title": "리뷰 평점 분포",
        "data": {"labels": labels, "values": values},
        "description": f"평균 평점 {avg_rating}점 (총 {total}개 리뷰). {max_rating}점 리뷰가 {max_pct}%로 가장 많습니다."
    }


@tool
def transform_review_stats_to_chart(
    avg_rating: Annotated[float, "평균 평점"],
    total_reviews: Annotated[int, "총 리뷰 수"],
    rating_distribution: Annotated[Dict[str, int], "평점별 리뷰 수 딕셔너리 (예: {'5': 100, '4': 50, ...})"]
) -> dict:
    """집계된 리뷰 통계를 평점 분포 차트로 변환합니다.
    
    get_aggregated_statistics 도구로 집계한 결과를 차트로 변환할 때 사용합니다.
    
    Returns:
        평점 분포 차트 블록 (bar)
    """
    labels = ["5점", "4점", "3점", "2점", "1점"]
    values = [
        rating_distribution.get("5", rating_distribution.get(5, 0)),
        rating_distribution.get("4", rating_distribution.get(4, 0)),
        rating_distribution.get("3", rating_distribution.get(3, 0)),
        rating_distribution.get("2", rating_distribution.get(2, 0)),
        rating_distribution.get("1", rating_distribution.get(1, 0)),
    ]
    
    # 가장 많은 평점 찾기
    max_idx = values.index(max(values)) if values else 0
    max_label = labels[max_idx]
    max_count = values[max_idx]
    max_pct = round(max_count / total_reviews * 100, 1) if total_reviews > 0 else 0
    
    return {
        "type": "chart",
        "chartType": "bar",
        "title": "리뷰 평점 분포",
        "data": {"labels": labels, "values": values},
        "description": f"평균 평점 {avg_rating}점 (총 {total_reviews}개 리뷰). {max_label} 리뷰가 {max_pct}%로 가장 많습니다."
    }


@tool
def transform_monthly_data_to_table(
    monthly_data: Annotated[List[Dict[str, Any]], "월별 데이터 리스트 (cri_ym 포함)"],
    value_columns: Annotated[List[str], "표시할 값 열 이름 리스트"],
    column_labels: Annotated[List[str], "열 헤더로 표시할 라벨 리스트"],
    title: Annotated[str, "표 제목"] = "월별 현황"
) -> dict:
    """월별 데이터를 테이블 블록으로 변환합니다.
    
    입력 예시:
    monthly_data = [{"cri_ym": 202410, "total": 320000}, {"cri_ym": 202411, "total": 285000}]
    value_columns = ["total"]
    column_labels = ["방문자수"]
    
    Returns:
        테이블 블록
    """
    if not monthly_data:
        return {
            "type": "table",
            "title": title,
            "headers": ["월"] + column_labels,
            "rows": [],
            "description": "데이터가 없습니다."
        }
    
    headers = ["월"] + column_labels
    rows = []
    
    for data in monthly_data:
        cri_ym = data.get("cri_ym", "")
        # YYYYMM 형식을 YYYY-MM으로 변환
        if cri_ym:
            year = str(cri_ym)[:4]
            month = str(cri_ym)[4:6]
            month_str = f"{year}-{month}"
        else:
            month_str = "-"
        
        row = [month_str]
        for col in value_columns:
            val = data.get(col, 0)
            # 숫자 포맷팅
            if isinstance(val, (int, float)):
                row.append(f"{val:,.0f}" if val >= 1000 else str(val))
            else:
                row.append(str(val) if val else "-")
        rows.append(row)
    
    return {
        "type": "table",
        "title": title,
        "headers": headers,
        "rows": rows,
        "description": f"총 {len(rows)}개월 데이터"
    }


@tool
def transform_visit_time_to_chart(
    persona_data: Annotated[Dict[str, Any], "persona_metrics 테이블에서 조회한 단일 레코드 (ct_XX_rt 포함)"]
) -> dict:
    """방문 시간대별 데이터를 막대 차트로 변환합니다.
    
    Returns:
        시간대별 방문 비율 차트 블록 (bar)
    """
    if not persona_data:
        return {
            "type": "chart",
            "chartType": "bar",
            "title": "시간대별 방문 비율",
            "data": {"labels": [], "values": []},
            "description": "데이터가 없습니다."
        }
    
    # 주요 시간대만 추출
    time_labels = ["6시", "9시", "12시", "15시", "18시", "21시"]
    time_keys = ["ct_06_rt", "ct_09_rt", "ct_12_rt", "ct_15_rt", "ct_18_rt", "ct_21_rt"]
    
    values = []
    for key in time_keys:
        val = float(persona_data.get(key, 0) or 0)
        values.append(round(val, 1))
    
    # 가장 높은 시간대 찾기
    max_idx = values.index(max(values)) if values else 0
    max_time = time_labels[max_idx]
    max_val = values[max_idx]
    
    return {
        "type": "chart",
        "chartType": "bar",
        "title": "시간대별 방문 비율",
        "data": {"labels": time_labels, "values": values},
        "description": f"{max_time} 방문이 {max_val}%로 가장 많습니다."
    }


@tool
def transform_weekday_to_chart(
    persona_data: Annotated[Dict[str, Any], "persona_metrics 테이블에서 조회한 단일 레코드 (ct_week_XX 포함)"]
) -> dict:
    """요일별 방문 데이터를 막대 차트로 변환합니다.
    
    Returns:
        요일별 방문 비율 차트 블록 (bar)
    """
    if not persona_data:
        return {
            "type": "chart",
            "chartType": "bar",
            "title": "요일별 방문 비율",
            "data": {"labels": [], "values": []},
            "description": "데이터가 없습니다."
        }
    
    labels = ["월", "화", "수", "목", "금", "토", "일"]
    keys = ["ct_week_01", "ct_week_02", "ct_week_03", "ct_week_04", "ct_week_05", "ct_week_06", "ct_week_07"]
    
    values = []
    for key in keys:
        val = float(persona_data.get(key, 0) or 0)
        values.append(round(val, 1))
    
    # 주말/평일 비교
    we_rt = float(persona_data.get("we_rt", 0) or 0)
    wk_rt = float(persona_data.get("wk_rt", 0) or 0)
    
    if we_rt > wk_rt:
        desc = f"주말 방문 비율({round(we_rt, 1)}%)이 평일({round(wk_rt, 1)}%)보다 높습니다."
    else:
        desc = f"평일 방문 비율({round(wk_rt, 1)}%)이 주말({round(we_rt, 1)}%)보다 높습니다."
    
    return {
        "type": "chart",
        "chartType": "bar",
        "title": "요일별 방문 비율",
        "data": {"labels": labels, "values": values},
        "description": desc
    }


# =============================================================================
# 헬퍼 함수
# =============================================================================

def _average_demographics(data_list: List[Dict[str, Any]]) -> Dict[str, float]:
    """여러 레코드의 평균값을 계산합니다."""
    if not data_list:
        return {}
    
    result = {}
    count = len(data_list)
    
    # 숫자형 컬럼만 평균 계산
    for key in data_list[0].keys():
        if key.startswith(("mrcno_pct_", "persona_pct_")):
            total = sum(float(d.get(key, 0) or 0) for d in data_list)
            result[key] = round(total / count, 2)
    
    return result


# 도구 리스트 (Analyse Agent에서 사용)
transform_tools = [
    transform_demographics_to_age_chart,
    transform_demographics_to_gender_chart,
    transform_reviews_to_rating_chart,
    transform_review_stats_to_chart,
    transform_monthly_data_to_table,
    transform_visit_time_to_chart,
    transform_weekday_to_chart,
]

