from __future__ import annotations
from langchain_core.tools import tool
from typing import Annotated, Any, Optional

from .api_utils import call_kcisa_api, call_kma_asos_daily_api, month_range
from .stellarcube_utils import get_monthly_age_gender_ratio
from .google_reviews_utils import get_google_map_rating_statistics


class ReportingTools:

    @staticmethod
    @tool
    def search_exhibition_info_api(
        keyword: Annotated[str, "전시 정보를 검색할 키워드 (기관명 사용, 예: 국립현대미술관, 국립중앙박물관)"] = "국립현대미술관",
        num_of_rows: Annotated[int, "조회할 데이터 행 수"] = 50
    ):
        """한국문화정보원 전시정보 통합 API (KCISA_CCA_145)를 검색합니다. 문화시설의 전시 정보, 이벤트, 프로그램 등을 조회합니다."""
        # keyword로만 API 호출 (filter_value 사용하지 않음)
        result = call_kcisa_api(
            api_name="KCISA_CCA_145",
            keyword=keyword,  # 서버 사이드 검색 파라미터
            filter_value=None,  # filter_value 사용하지 않음
            num_of_rows=num_of_rows,
            filter_remove_fields=False  # DESCRIPTION 포함
        )
        
        if result["success"]:
            return {
                "notes": f"{result['api_description']} 검색 완료: 총 {result['count']}개의 전시 정보를 찾았습니다.",
                "sources": [item.get("URL") for item in result["data"] if item.get("URL")],
                "data": result["data"]
            }
        else:
            return {
                "notes": f"전시 정보 검색 실패: {result.get('error', '알 수 없는 오류')}",
                "sources": [],
                "data": []
            }

    @staticmethod
    @tool
    def search_museum_collection_api(
        keyword: Annotated[str, "소장품을 검색할 키워드 (예: 청자, 호랑이, 불상 등)"] = "청자",
        num_of_rows: Annotated[int, "조회할 데이터 행 수"] = 50
    ):
        """국립중앙박물관 소장품 검색 API (KCISA_CPM_003)를 검색합니다. 박물관 소장품의 상세 정보를 조회합니다."""
        result = call_kcisa_api(
            api_name="KCISA_CPM_003",
            filter_value=keyword,
            num_of_rows=num_of_rows,
            filter_remove_fields=False  # DESCRIPTION 포함
        )
        
        # 성공/실패 여부와 함께 API 결과를 그대로 반환
        if result["success"]:
            return {
                "notes": f"{result['api_description']} 검색 완료: 총 {result['count']}개의 소장품 정보를 찾았습니다.",
                "sources": [item.get("url") for item in result["data"] if item.get("url")],
                "data": result["data"]
            }
        else:
            return {
                "notes": f"소장품 검색 실패: {result.get('error', '알 수 없는 오류')}",
                "sources": [],
                "data": []
            }

    @staticmethod
    @tool
    def search_performance_info_api(
        keyword: Annotated[str, "공연 정보를 검색할 키워드 (예: 예술의전당, 연극, 콘서트 등)"] = "예술의전당",
        num_of_rows: Annotated[int, "조회할 데이터 행 수"] = 50
    ):
        """
        한국문화정보원 공연정보 통합 API(KCISA_CCA_144)를 조회합니다.
        fields 예: TITLE, DESCRIPTION, IMAGE_OBJECT, LOCAL_ID, EVENT_SITE, GENRE, DURATION,
                  AUTHOR, ACTOR, CONTRIBUTOR, AUDIENCE, CHARGE, PERIOD, EVENT_PERIOD
        """
        # 예술의전당인 경우 컨텍스트 길이 초과 방지를 위해 10개로 제한
        if keyword and ("예술의전당" in keyword or "예술의 전당" in keyword):
            num_of_rows = min(num_of_rows, 10)
        
        result = call_kcisa_api(
            api_name="KCISA_CCA_144",
            keyword=keyword,     # filter_rules[0].value(CNTC_INSTT_NM)로도 필터링 됨
            num_of_rows=num_of_rows,
            filter_remove_fields=False  # DESCRIPTION 포함
        )

        if result.get("success"):
            data = result.get("data", [])

            # URL이 응답에 없을 수도 있으므로(확실하지 않음) 대체 가능 키로 소스 구성
            def pick_source(it: dict):
                return it.get("URL") or it.get("IMAGE_OBJECT") or it.get("LOCAL_ID")

            sources = [pick_source(it) for it in data if pick_source(it)]

            return {
                "notes": f"{result.get('api_description','공연정보')} 검색 완료: 총 {result.get('count', 0)}개의 공연 정보를 찾았습니다.",
                "sources": sources,
                "data": data
            }
        else:
            return {
                "notes": f"공연 정보 검색 실패: {result.get('error', '알 수 없는 오류')}",
                "sources": [],
                "data": []
            }

    @staticmethod
    @tool
    def search_weather_daily_api(
        year: Annotated[int, "연도"] = 2025,
        month: Annotated[int, "월(1~12)"] = 1,
        stn_ids: Annotated[str, "지점코드(예: 108=서울)"] = "108",
        num_of_rows: Annotated[int, "행 수"] = 999,
    ):
        """KMA ASOS 일자료(일별)를 월 단위로 조회하는 툴. tm/sumRn/maxTa/minTa 필드를 반환합니다."""
        try:
            start_dt, end_dt = month_range(year, month)  # ← 네 함수명과 일치
        except ValueError as e:
            return {"notes": f"입력 오류: {e}", "sources": [], "data": []}

        result = call_kma_asos_daily_api(start_dt, end_dt, stn_ids, num_of_rows)
        if result["success"]:
            return {"notes": f"{result['api_description']} {year}년 {month}월 조회 완료: 총 {result['count']}개의 일자료.", "sources": [], "data": result["data"]}
        else:
            return {"notes": f"날씨 데이터 조회 실패: {result.get('error', '알 수 없는 오류')}", "sources": [], "data": []}

    @staticmethod
    @tool
    def get_monthly_age_gender_ratio_data(
        organization_name: Annotated[str, "기관명 (예: 국립현대미술관, 국립중앙박물관, 예술의전당)"] = "국립현대미술관",
        year: Annotated[Optional[int], "조회할 연도 (None이면 전체)"] = None,
        month: Annotated[Optional[int], "조회할 월 (None이면 전체)"] = None
    ):
        """
        AWS RDS 데이터베이스에서 월별 남성/여성 연령대 비율 데이터를 조회합니다.
        기관별 방문자의 연령대별 성별 비율을 월별로 집계하여 반환합니다.
        
        지원 기관:
        - 국립현대미술관 → 국립현대미술관서울관 데이터 조회
        - 국립중앙박물관 → 국립중앙박물관 데이터 조회
        - 예술의전당 → 예술의전당한가람미술관 데이터 조회
        """
        result = get_monthly_age_gender_ratio(organization_name, year, month)
        
        if result["success"]:
            notes = f"{result['organization_name']} 월별 연령대별 성별 비율 데이터 조회 완료: 총 {result['count']}개월 데이터"
            if year:
                notes += f" ({year}년"
                if month:
                    notes += f" {month}월"
                notes += ")"
            
            return {
                "notes": notes,
                "sources": [],
                "data": result["data"],
                "chart_data": result["data"]  # 차트용 데이터 별도 포함
            }
        else:
            return {
                "notes": f"월별 연령대별 성별 비율 데이터 조회 실패: {result.get('error', '알 수 없는 오류')}",
                "sources": [],
                "data": [],
                "chart_data": []
            }

    @staticmethod
    @tool
    def get_google_map_rating_statistics(
        organization_name: Annotated[str, "기관명 (예: 국립현대미술관, 국립중앙박물관, 예술의전당)"] = "국립현대미술관"
    ):
        """
        AWS RDS 데이터베이스에서 구글맵 리뷰 평점 통계를 조회합니다.
        기관별 구글맵 리뷰의 평점 분포와 평균 평점을 계산하여 반환합니다.
        
        반환 데이터:
        - total_reviews: 총 리뷰 수
        - average_rating: 평균 평점 (1.0 ~ 5.0)
        - rating_distribution: 평점별 리뷰 수 (1점, 2점, 3점, 4점, 5점)
        - rating_percentages: 평점별 비율 (%)
        """
        result = get_google_map_rating_statistics(organization_name)
        
        if result["success"]:
            stats = result["data"]
            notes = f"{result['organization_name']} 구글맵 리뷰 평점 통계 조회 완료: 총 {stats['total_reviews']}개 리뷰, 평균 평점 {stats['average_rating']}/5.0"
            
            return {
                "notes": notes,
                "sources": [],
                "data": stats,
                "rating_statistics": stats  # 평점 통계 데이터 별도 포함
            }
        else:
            return {
                "notes": f"구글맵 리뷰 평점 통계 조회 실패: {result.get('error', '알 수 없는 오류')}",
                "sources": [],
                "data": {},
                "rating_statistics": {}
            }