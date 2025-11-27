"""Server-Driven Report UI를 위한 블록 생성 도구

이 모듈은 LangChain @tool로 래핑된 블록 생성 함수들을 제공합니다.
Analyse Agent가 이 도구들을 호출하여 보고서 블록을 생성합니다.
"""

from typing import List, Annotated
from langchain_core.tools import tool


@tool
def create_markdown_block(
    content: Annotated[str, "마크다운 형식의 텍스트 내용 (제목, 본문, 목록 등)"]
) -> dict:
    """마크다운 텍스트 블록을 생성합니다.
    
    사용 예시:
    - 섹션 제목: "## 1. 개요"
    - 본문 텍스트: "국립중앙박물관은..."
    - 목록: "- 항목1\n- 항목2"
    
    Returns:
        {"type": "markdown", "content": "..."}
    """
    return {"type": "markdown", "content": content}


@tool
def create_chart_block(
    chart_type: Annotated[str, "차트 유형: doughnut, bar, line, pie, radar 중 하나"],
    title: Annotated[str, "차트 제목"],
    labels: Annotated[List[str], "데이터 라벨 배열 (예: ['20대', '30대', '40대'])"],
    values: Annotated[List[float], "데이터 값 배열 (예: [25, 35, 22])"],
    description: Annotated[str, "차트에 대한 설명 텍스트"] = ""
) -> dict:
    """Chart.js 차트 블록을 생성합니다.
    
    차트 유형별 권장 용도:
    - doughnut/pie: 비율 표시 (연령대별, 성별 분포)
    - bar: 항목 비교 (월별 방문자, 평점 분포)
    - line: 시계열 추이 (월별 변화)
    - radar: 다차원 비교 (페르소나 특성)
    
    Returns:
        {"type": "chart", "chartType": "...", "title": "...", "data": {...}, "description": "..."}
    """
    # 유효한 차트 타입 검증
    valid_types = ["doughnut", "bar", "line", "pie", "radar", "polarArea"]
    if chart_type not in valid_types:
        chart_type = "bar"  # 기본값
    
    return {
        "type": "chart",
        "chartType": chart_type,
        "title": title,
        "data": {"labels": labels, "values": values},
        "description": description
    }


@tool
def create_table_block(
    title: Annotated[str, "표 제목"],
    headers: Annotated[List[str], "열 헤더 배열 (예: ['월', '방문자수', '전년대비'])"],
    rows: Annotated[List[List[str]], "행 데이터 2차원 배열 (예: [['10월', '320,000', '+12%'], ...])"],
    description: Annotated[str, "표에 대한 설명 텍스트"] = ""
) -> dict:
    """표 블록을 생성합니다.
    
    표는 상세 정보를 체계적으로 정리할 때 사용합니다.
    - 월별 현황
    - 항목별 비교
    - 상세 데이터 목록
    
    Returns:
        {"type": "table", "title": "...", "headers": [...], "rows": [[...]], "description": "..."}
    """
    return {
        "type": "table",
        "title": title,
        "headers": headers,
        "rows": rows,
        "description": description
    }


@tool
def create_image_block(
    url: Annotated[str, "이미지 URL"],
    alt: Annotated[str, "이미지 대체 텍스트 (접근성용)"],
    caption: Annotated[str, "이미지 캡션 (선택)"] = ""
) -> dict:
    """이미지 블록을 생성합니다.
    
    전시/공연 포스터, 시설 사진 등을 표시할 때 사용합니다.
    
    Returns:
        {"type": "image", "url": "...", "alt": "...", "caption": "..."}
    """
    return {
        "type": "image",
        "url": url,
        "alt": alt,
        "caption": caption
    }


@tool
def create_map_block(
    title: Annotated[str, "지도 제목 (예: '시설 위치')"],
    center_lat: Annotated[float, "지도 중심 위도"],
    center_lng: Annotated[float, "지도 중심 경도"],
    zoom: Annotated[int, "지도 줌 레벨 (1-20, 기본 15)"] = 15,
    markers: Annotated[List[dict], "마커 목록 [{lat, lng, label, type?}, ...]"] = None,
    description: Annotated[str, "지도 설명 텍스트"] = ""
) -> dict:
    """인터랙티브 지도 블록을 생성합니다.
    
    시설 위치, 주변 장소 등을 지도에 표시할 때 사용합니다.
    프론트엔드에서 Google Maps JavaScript API로 렌더링됩니다.
    
    마커 타입: 'facility' (기본), 'restaurant', 'attraction', 'transit'
    
    Returns:
        {"type": "map", "title": "...", "center": {lat, lng}, "zoom": 15, "markers": [...]}
    """
    return {
        "type": "map",
        "title": title,
        "center": {"lat": center_lat, "lng": center_lng},
        "zoom": zoom,
        "markers": markers or [],
        "description": description
    }


@tool
def create_air_quality_block(
    title: Annotated[str, "블록 제목 (예: '대기질 정보')"],
    aqi: Annotated[int, "AQI 지수 (0-500)"],
    category: Annotated[str, "등급 (좋음/보통/민감군나쁨/나쁨/매우나쁨)"],
    pm25: Annotated[float, "PM2.5 농도 (µg/m³)"] = None,
    pm10: Annotated[float, "PM10 농도 (µg/m³)"] = None,
    recommendation: Annotated[str, "건강 권고사항"] = "",
    description: Annotated[str, "추가 설명"] = ""
) -> dict:
    """대기질 정보 블록을 생성합니다.
    
    야외활동 적합도 등 방문 환경 정보를 제공할 때 사용합니다.
    
    AQI 등급:
    - 1 (0-50): 좋음 (녹색)
    - 2 (51-100): 보통 (노랑)
    - 3 (101-150): 민감군나쁨 (주황)
    - 4 (151-200): 나쁨 (빨강)
    - 5 (201+): 매우나쁨 (자주)
    
    Returns:
        {"type": "air_quality", "title": "...", "aqi": 45, "category": "좋음", ...}
    """
    # AQI에 따른 색상 결정
    color_map = {
        "좋음": "#00E400",
        "보통": "#FFFF00", 
        "민감군나쁨": "#FF7E00",
        "나쁨": "#FF0000",
        "매우나쁨": "#7E0023"
    }
    
    return {
        "type": "air_quality",
        "title": title,
        "aqi": aqi,
        "category": category,
        "category_color": color_map.get(category, "#808080"),
        "pollutants": {
            "pm25": pm25,
            "pm10": pm10
        },
        "recommendation": recommendation,
        "description": description
    }


# 도구 리스트 (Analyse Agent에서 사용)
block_tools = [
    create_markdown_block,
    create_chart_block,
    create_table_block,
    create_image_block,
    create_map_block,
    create_air_quality_block,
]

