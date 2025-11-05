from langchain_core.tools import tool
from typing import Annotated

from .api_utils import call_kcisa_api


class ReportingTools:

    @staticmethod
    @tool
    def search_exhibition_info_api(
        keyword: Annotated[str, "전시 정보를 검색할 키워드 (예: www.museum.go.kr)"] = "www.museum.go.kr",
        num_of_rows: Annotated[int, "조회할 데이터 행 수"] = 50
    ):
        """한국문화정보원 전시정보 통합 API (KCISA_CCA_145)를 검색합니다. 문화시설의 전시 정보, 이벤트, 프로그램 등을 조회합니다."""
        result = call_kcisa_api(
            api_name="KCISA_CCA_145",
            filter_value=keyword,
            num_of_rows=num_of_rows
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
            num_of_rows=num_of_rows
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
    def search_internal_documents(
        query: Annotated[str, "검색할 내부 데이터에 대한 질문."],
        limit: Annotated[int, "Maximum number of items to retrieve."] = 5
    ):
        """내부 지식 기반에서 보고서에 관련된 자료를 검색하는 코드 구현 예정""" 
        return {
            "notes": "내부 문서 검색 기능은 아직 구현되지 않았습니다.",
            "sources": []
        }

    @staticmethod
    @tool
    def fetch_data_snapshot(
        dataset: Annotated[str, "가져올 데이터셋의 식별자."],
        window: Annotated[str, "Desired time range for the snapshot."] = "latest"
    ):
        """구조화된 데이터 스냅샷을 가져와 후속 분석에 사용할 수 있도록 하는 코드 구현 예정"""
        return {
            "notes": "데이터 스냅샷 기능은 아직 구현되지 않았습니다.",
            "sources": []
        }

    @staticmethod
    @tool
    def analyse_quantitative_metrics(
        data_reference: Annotated[str, "검토 중인 데이터셋에 대한 참고 자료."]
    ):
        """수집된 지표에 대해 양적 분석을 실행하는 코드 구현 예정"""
        return {
            "analysis_notes": "정량적 지표 분석 기능은 아직 구현되지 않았습니다."
        }

    @staticmethod
    @tool
    def analyse_qualitative_feedback(
        notes: Annotated[str, "조사 메모를 통합한 검토 자료."]
    ):
        """인터뷰나 텍스트 요약과 같은 질적 입력을 검토하는 코드 구현 예정"""
        return {
            "analysis_notes": "정성적 피드백 분석 기능은 아직 구현되지 않았습니다."
        }
