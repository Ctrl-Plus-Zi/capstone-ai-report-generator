from langchain_core.tools import tool
from typing import Annotated


class ReportingTools:

    @staticmethod
    @tool
    def search_internal_documents(query: Annotated[str, "검색할 내부 데이터에 대한 질문."],
                                  limit: Annotated[int, "Maximum number of items to retrieve."] = 5):
        """내부 지식 기반에서 보고서에 관련된 자료를 검색하는 코드 구현 예정""" 
        pass


    @staticmethod
    @tool
    def search_external_api(query: Annotated[str, "검색할 외부 API에 대한 질문."],
                            source: Annotated[str, "External API identifier."] = "public_api"):
        """외부 API를 통해 최신 참고 자료를 검색하는 코드 구현 예정"""
        pass


    @staticmethod
    @tool
    def fetch_data_snapshot(dataset: Annotated[str, "가져올 데이터셋의 식별자."],
                             window: Annotated[str, "Desired time range for the snapshot."] = "latest"):
        """구조화된 데이터 스냅샷을 가져와 후속 분석에 사용할 수 있도록 하는 코드 구현 예정"""
        pass


    @staticmethod
    @tool
    def analyse_quantitative_metrics(data_reference: Annotated[str, "검토 중인 데이터셋에 대한 참고 자료."]):
        """수집된 지표에 대해 양적 분석을 실행하는 코드 구현 예정"""
        pass


    @staticmethod
    @tool
    def analyse_qualitative_feedback(notes: Annotated[str, "조사 메모를 통합한 검토 자료."]):
        """인터뷰나 텍스트 요약과 같은 질적 입력을 검토하는 코드 구현 예정"""
        pass
