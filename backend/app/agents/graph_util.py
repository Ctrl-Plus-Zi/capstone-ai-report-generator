from langchain_core.tools import tool
from typing import Annotated


class ReportingTools:
    """에이전트가 활용할 조사·분석용 도구 모음 (임시 구현)."""

    @staticmethod
    @tool
    def search_internal_documents(query: Annotated[str, "필요한 내부 자료를 설명하는 질의어."],
                                  limit: Annotated[int, "최대 조회 건수."] = 5):
        """사내 문서를 검색해 보고서에 활용할 자료를 찾습니다."""
        pass

    @staticmethod
    @tool
    def search_external_api(query: Annotated[str, "외부 API 검색을 위한 질의."],
                            source: Annotated[str, "호출할 외부 API 식별자."] = "public_api"):
        """외부 API를 호출해 최신 참고 자료를 확보합니다."""
        pass

    @staticmethod
    @tool
    def fetch_data_snapshot(dataset: Annotated[str, "가져올 데이터셋 식별자."],
                             window: Annotated[str, "요청할 기간 또는 시점."] = "latest"):
        """추가 분석을 위해 구조화된 데이터 스냅샷을 수집합니다."""
        pass

    @staticmethod
    @tool
    def analyse_quantitative_metrics(data_reference: Annotated[str, "분석 대상 데이터 식별자."]):
        """수집된 지표에 대해 정량 분석을 수행합니다."""
        pass

    @staticmethod
    @tool
    def analyse_qualitative_feedback(notes: Annotated[str, "조사 노트를 모아둔 텍스트."]):
        """인터뷰·기사 등 정성적 자료를 검토해 통찰을 도출합니다."""
        pass
