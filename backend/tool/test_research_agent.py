"""
리서치 에이전트 디버깅 스크립트
기관명과 질문을 입력받아 리서치 에이전트만 실행하고 결과를 출력합니다.
API 호출 과정도 상세히 출력합니다.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    print("⚠️  tiktoken이 설치되지 않아 토큰 수 계산이 정확하지 않을 수 있습니다. 설치: pip install tiktoken")

# 프로젝트 루트를 Python 경로에 추가
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from typing import Annotated
from app.agents.search_agent import create_search_agent
from app.agents.agent_state import ReportingAgentState
from app.agents.graph_util import ReportingTools
from app.config import settings

# 전역 변수: DESCRIPTION 포함 여부
include_description = False

# 토큰 수 계산 함수
def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """텍스트의 토큰 수를 계산합니다."""
    if not TIKTOKEN_AVAILABLE:
        # 대략적인 추정: 공백 기준으로 단어 수를 세고 1.3을 곱함 (한국어는 더 복잡하지만 근사치)
        return int(len(text.split()) * 1.3)
    
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except:
        # 모델을 찾을 수 없으면 cl100k_base 인코딩 사용 (gpt-4, gpt-3.5-turbo 등)
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

# API 호출을 추적하기 위한 래퍼 함수
from app.agents.api_utils import call_kcisa_api, call_kma_asos_daily_api

_original_call_kcisa_api = call_kcisa_api
_original_call_kma_asos_daily_api = call_kma_asos_daily_api

def _debug_call_kcisa_api(*args, **kwargs):
    """API 호출을 추적하는 래퍼"""
    api_name = kwargs.get('api_name') or (args[0] if args else 'N/A')
    keyword = kwargs.get('keyword')
    filter_value = kwargs.get('filter_value')
    num_of_rows = kwargs.get('num_of_rows', 50)
    page_no = kwargs.get('page_no', 1)
    
    print("\n" + "="*80)
    print(f"🌐 [API 호출 시작] {api_name}")
    print("-" * 80)
    print(f"   파라미터:")
    print(f"     - keyword: {keyword}")
    print(f"     - filter_value: {filter_value}")
    print(f"     - num_of_rows: {num_of_rows}")
    print(f"     - page_no: {page_no}")
    print("="*80)
    
    result = _original_call_kcisa_api(*args, **kwargs)
    
    print(f"\n📡 [API 호출 결과] {api_name}")
    print("-" * 80)
    if result.get('url'):
        print(f"   호출 URL: {result['url']}")
    print(f"   성공 여부: {result.get('success', False)}")
    if result.get('success'):
        print(f"   데이터 개수: {result.get('count', 0)}")
        print(f"   API 설명: {result.get('api_description', 'N/A')}")
    else:
        print(f"   오류: {result.get('error', 'N/A')}")
    print("="*80 + "\n")
    
    return result

def _debug_call_kma_asos_daily_api(*args, **kwargs):
    """기상청 API 호출을 추적하는 래퍼"""
    start_dt = kwargs.get('start_dt') or (args[0] if args else 'N/A')
    end_dt = kwargs.get('end_dt') or (args[1] if len(args) > 1 else 'N/A')
    stn_ids = kwargs.get('stn_ids', '108')
    num_of_rows = kwargs.get('num_of_rows', 999)
    
    print("\n" + "="*80)
    print("🌐 [API 호출 시작] KMA_ASOS_DAILY (기상청 일자료)")
    print("-" * 80)
    print(f"   파라미터:")
    print(f"     - start_dt: {start_dt}")
    print(f"     - end_dt: {end_dt}")
    print(f"     - stn_ids: {stn_ids}")
    print(f"     - num_of_rows: {num_of_rows}")
    print("="*80)
    
    result = _original_call_kma_asos_daily_api(*args, **kwargs)
    
    print(f"\n📡 [API 호출 결과] KMA_ASOS_DAILY")
    print("-" * 80)
    print(f"   성공 여부: {result.get('success', False)}")
    if result.get('success'):
        print(f"   데이터 개수: {result.get('count', 0)}")
        print(f"   API 설명: {result.get('api_description', 'N/A')}")
        if result.get('result_code'):
            print(f"   결과 코드: {result.get('result_code')}")
            print(f"   결과 메시지: {result.get('result_msg', 'N/A')}")
    else:
        print(f"   오류: {result.get('error', 'N/A')}")
    print("="*80 + "\n")
    
    return result

# Monkey patch으로 API 호출 함수 교체
import app.agents.api_utils as api_utils_module
api_utils_module.call_kcisa_api = _debug_call_kcisa_api
api_utils_module.call_kma_asos_daily_api = _debug_call_kma_asos_daily_api


# API 호출을 추적하기 위한 래퍼 클래스
class DebugReportingTools(ReportingTools):
    """API 호출을 추적하는 ReportingTools 래퍼"""
    
    @staticmethod
    @tool
    def search_exhibition_info_api(
        keyword: Annotated[str, "전시 정보를 검색할 키워드 (예: www.museum.go.kr)"] = "www.museum.go.kr",
        num_of_rows: Annotated[int, "조회할 데이터 행 수"] = 50
    ):
        """한국문화정보원 전시정보 통합 API (KCISA_CCA_145)를 검색합니다. 문화시설의 전시 정보, 이벤트, 프로그램 등을 조회합니다."""
        print("\n" + "="*80)
        print("🔍 [도구 호출] search_exhibition_info_api")
        print(f"   키워드: {keyword}")
        print(f"   행 수: {num_of_rows}")
        print("="*80)
        # 원본 함수의 실제 구현을 직접 호출 (콜백 충돌 방지)
        from app.agents.api_utils import call_kcisa_api
        # 전역 변수에서 include_description 가져오기
        global include_description
        # keyword가 URL 패턴인 경우 기관명으로 변환 시도
        filter_value = None
        if keyword and ("www." in keyword or ".go.kr" in keyword or ".kr" in keyword):
            # URL 패턴인 경우, filter_value로만 사용 (서버 사이드 검색은 하지 않음)
            filter_value = keyword
            keyword = None
        # 기관명인 경우 keyword로만 서버 사이드 검색 사용 (filter_value는 사용하지 않음)
        # 서버 사이드 검색이 이미 기관명으로 필터링하므로 중복 필터링 불필요
        
        api_result = call_kcisa_api(
            api_name="KCISA_CCA_145",
            keyword=keyword,  # 서버 사이드 검색 파라미터 (기관명인 경우만)
            filter_value=filter_value,  # 클라이언트 사이드 필터링 (URL인 경우만)
            num_of_rows=num_of_rows,
            filter_remove_fields=not include_description
        )
        
        if api_result["success"]:
            result = {
                "notes": f"{api_result['api_description']} 검색 완료: 총 {api_result['count']}개의 전시 정보를 찾았습니다.",
                "sources": [item.get("URL") for item in api_result["data"] if item.get("URL")],
                "data": api_result["data"]
            }
        else:
            result = {
                "notes": f"전시 정보 검색 실패: {api_result.get('error', '알 수 없는 오류')}",
                "sources": [],
                "data": []
            }
        print(f"✅ 도구 실행 완료: {result.get('notes', 'N/A')}")
        print(f"   반환된 데이터 개수: {len(result.get('data', []))}")
        if result.get('data'):
            print(f"   샘플 데이터 (첫 1개):")
            print(json.dumps(result['data'][0], ensure_ascii=False, indent=4))
        print("="*80 + "\n")
        return result
    
    @staticmethod
    @tool
    def search_museum_collection_api(
        keyword: Annotated[str, "소장품을 검색할 키워드 (예: 청자, 호랑이, 불상 등)"] = "청자",
        num_of_rows: Annotated[int, "조회할 데이터 행 수"] = 50
    ):
        """국립중앙박물관 소장품 검색 API (KCISA_CPM_003)를 검색합니다. 박물관 소장품의 상세 정보를 조회합니다."""
        print("\n" + "="*80)
        print("🔍 [도구 호출] search_museum_collection_api")
        print(f"   키워드: {keyword}")
        print(f"   행 수: {num_of_rows}")
        print("="*80)
        # 원본 함수의 실제 구현을 직접 호출 (콜백 충돌 방지)
        from app.agents.api_utils import call_kcisa_api
        api_result = call_kcisa_api(
            api_name="KCISA_CPM_003",
            filter_value=keyword,
            num_of_rows=num_of_rows
        )
        
        if api_result["success"]:
            result = {
                "notes": f"{api_result['api_description']} 검색 완료: 총 {api_result['count']}개의 소장품 정보를 찾았습니다.",
                "sources": [item.get("url") for item in api_result["data"] if item.get("url")],
                "data": api_result["data"]
            }
        else:
            result = {
                "notes": f"소장품 검색 실패: {api_result.get('error', '알 수 없는 오류')}",
                "sources": [],
                "data": []
            }
        print(f"✅ 도구 실행 완료: {result.get('notes', 'N/A')}")
        print(f"   반환된 데이터 개수: {len(result.get('data', []))}")
        if result.get('data'):
            print(f"   샘플 데이터 (첫 1개):")
            print(json.dumps(result['data'][0], ensure_ascii=False, indent=4))
        print("="*80 + "\n")
        return result
    
    @staticmethod
    @tool
    def search_performance_info_api(
        keyword: Annotated[str, "공연 정보를 검색할 키워드 (예: 예술의전당, 연극, 콘서트 등)"] = "예술의전당",
        num_of_rows: Annotated[int, "조회할 데이터 행 수"] = 50
    ):
        """한국문화정보원 공연정보 통합 API(KCISA_CCA_144)를 조회합니다."""
        print("\n" + "="*80)
        print("🔍 [도구 호출] search_performance_info_api")
        print(f"   키워드: {keyword}")
        # 예술의전당인 경우 10개로 제한
        if "예술의전당" in keyword or "예술의 전당" in keyword:
            num_of_rows = min(num_of_rows, 10)
            print(f"   행 수: {num_of_rows} (예술의전당이므로 최대 10개로 제한)")
        else:
            print(f"   행 수: {num_of_rows}")
        print("="*80)
        # 원본 함수의 실제 구현을 직접 호출 (콜백 충돌 방지)
        from app.agents.api_utils import call_kcisa_api
        # 전역 변수에서 include_description 가져오기
        global include_description
        api_result = call_kcisa_api(
            api_name="KCISA_CCA_144",
            keyword=keyword,
            num_of_rows=num_of_rows,
            filter_remove_fields=not include_description
        )
        
        if api_result.get("success"):
            data = api_result.get("data", [])
            def pick_source(it: dict):
                return it.get("URL") or it.get("IMAGE_OBJECT") or it.get("LOCAL_ID")
            sources = [pick_source(it) for it in data if pick_source(it)]
            result = {
                "notes": f"{api_result.get('api_description','공연정보')} 검색 완료: 총 {api_result.get('count', 0)}개의 공연 정보를 찾았습니다.",
                "sources": sources,
                "data": data
            }
        else:
            result = {
                "notes": f"공연 정보 검색 실패: {api_result.get('error', '알 수 없는 오류')}",
                "sources": [],
                "data": []
            }
        print(f"✅ 도구 실행 완료: {result.get('notes', 'N/A')}")
        print(f"   반환된 데이터 개수: {len(result.get('data', []))}")
        if result.get('data'):
            print(f"   샘플 데이터 (첫 1개):")
            print(json.dumps(result['data'][0], ensure_ascii=False, indent=4))
        print("="*80 + "\n")
        return result
    
    @staticmethod
    @tool
    def search_weather_daily_api(
        year: Annotated[int, "연도"] = 2025,
        month: Annotated[int, "월(1~12)"] = 1,
        stn_ids: Annotated[str, "지점코드(예: 108=서울)"] = "108",
        num_of_rows: Annotated[int, "행 수"] = 999,
    ):
        """KMA ASOS 일자료(일별)를 월 단위로 조회하는 툴. tm/sumRn/maxTa/minTa 필드를 반환합니다."""
        print("\n" + "="*80)
        print("🔍 [도구 호출] search_weather_daily_api")
        print(f"   연도: {year}")
        print(f"   월: {month}")
        print(f"   지점코드: {stn_ids}")
        print(f"   행 수: {num_of_rows}")
        print("="*80)
        # 원본 함수의 실제 구현을 직접 호출 (콜백 충돌 방지)
        from app.agents.api_utils import call_kma_asos_daily_api, month_range
        try:
            start_dt, end_dt = month_range(year, month)
        except ValueError as e:
            result = {"notes": f"입력 오류: {e}", "sources": [], "data": []}
        else:
            api_result = call_kma_asos_daily_api(start_dt, end_dt, stn_ids, num_of_rows)
            if api_result["success"]:
                result = {
                    "notes": f"{api_result['api_description']} {year}년 {month}월 조회 완료: 총 {api_result['count']}개의 일자료.",
                    "sources": [],
                    "data": api_result["data"]
                }
            else:
                result = {
                    "notes": f"날씨 데이터 조회 실패: {api_result.get('error', '알 수 없는 오류')}",
                    "sources": [],
                    "data": []
                }
        print(f"✅ 도구 실행 완료: {result.get('notes', 'N/A')}")
        print(f"   반환된 데이터 개수: {len(result.get('data', []))}")
        if result.get('data'):
            print(f"   샘플 데이터 (첫 1개):")
            print(json.dumps(result['data'][0], ensure_ascii=False, indent=4))
        print("="*80 + "\n")
        return result
    
    @staticmethod
    @tool
    def search_internal_documents(
        query: Annotated[str, "검색할 내부 데이터에 대한 질문."],
        limit: Annotated[int, "Maximum number of items to retrieve."] = 5
    ):
        """내부 지식 기반에서 보고서에 관련된 자료를 검색하는 코드 구현 예정"""
        print("\n" + "="*80)
        print("🔍 [도구 호출] search_internal_documents")
        print(f"   쿼리: {query}")
        print(f"   제한: {limit}")
        print("="*80)
        # 원본 함수의 실제 구현을 직접 호출 (콜백 충돌 방지)
        result = {
            "notes": "내부 문서 검색 기능은 아직 구현되지 않았습니다.",
            "sources": []
        }
        print(f"✅ 도구 실행 완료: {result.get('notes', 'N/A')}")
        print("="*80 + "\n")
        return result
    
    @staticmethod
    @tool
    def fetch_data_snapshot(
        dataset: Annotated[str, "가져올 데이터셋의 식별자."],
        window: Annotated[str, "Desired time range for the snapshot."] = "latest"
    ):
        """구조화된 데이터 스냅샷을 가져와 후속 분석에 사용할 수 있도록 하는 코드 구현 예정"""
        print("\n" + "="*80)
        print("🔍 [도구 호출] fetch_data_snapshot")
        print(f"   데이터셋: {dataset}")
        print(f"   윈도우: {window}")
        print("="*80)
        # 원본 함수의 실제 구현을 직접 호출 (콜백 충돌 방지)
        result = {
            "notes": "데이터 스냅샷 기능은 아직 구현되지 않았습니다.",
            "sources": []
        }
        print(f"✅ 도구 실행 완료: {result.get('notes', 'N/A')}")
        print("="*80 + "\n")
        return result


def main():
    print("\n" + "="*80)
    print("리서치 에이전트 디버깅 스크립트")
    print("="*80 + "\n")
    
    # 환경 변수 확인
    if not settings.openai_api_key:
        print("❌ 오류: OPENAI_API_KEY가 설정되지 않았습니다.")
        print("   .env 파일을 확인하세요.")
        return
    
    # 사용자 입력 받기
    organization_name = input("기관명>> ").strip()
    if not organization_name:
        print("❌ 기관명을 입력해주세요.")
        return
    
    question = input("질문>> ").strip()
    if not question:
        print("❌ 질문을 입력해주세요.")
        return
    
    # DESCRIPTION 항상 포함
    global include_description
    include_description = True
    
    # 오늘 날짜 가져오기
    today = datetime.now()
    current_date = today.strftime("%Y-%m-%d")
    current_year = today.year
    current_month = today.month
    
    print(f"\n📅 오늘 날짜: {current_date} (자동으로 현재 진행 중인 공연/전시만 필터링됩니다)")
    
    print("\n" + "="*80)
    print("리서치 에이전트 실행 중...")
    print("="*80 + "\n")
    
    # LLM 초기화
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        api_key=settings.openai_api_key,
    )
    
    # 디버깅용 툴킷 초기화
    toolkit = DebugReportingTools()
    
    # 리서치 에이전트 생성
    search_agent = create_search_agent(llm, toolkit)
    
    # 초기 상태 설정 (오늘 날짜 포함)
    initial_state: ReportingAgentState = {
        "request_context": {
            "organization_name": organization_name,
            "report_topic": question,
            "questions": [question],
            "current_date": current_date,  # 오늘 날짜 추가
            "current_year": current_year,
            "current_month": current_month,
            "filter_active_only": True,  # 현재 진행 중인 것만 필터링 플래그
        },
        "messages": [HumanMessage(content=f"{question} (오늘 날짜: {current_date}, 현재 진행 중인 공연/전시만 포함해주세요)")],
        "research_notes": "",
        "research_sources": [],
        "research_payload": [],
    }
    
    print("\n" + "="*80)
    print("📋 요청 컨텍스트")
    print("="*80)
    print(json.dumps(initial_state["request_context"], ensure_ascii=False, indent=2))
    print("="*80 + "\n")
    
    # 리서치 에이전트 실행
    try:
        result_state = search_agent(initial_state)
        
        print("\n" + "="*80)
        print("📊 리서치 에이전트 실행 결과")
        print("="*80)
        
        # 토큰 수 계산
        print("\n[토큰 수 분석]")
        print("-" * 80)
        
        # 리서치 에이전트가 입력받는 데이터 (ToolMessage 내 전체 데이터)
        messages = result_state.get("messages", [])
        tool_messages_data_tokens = 0
        tool_messages_full_tokens = 0  # ToolMessage 전체 (data + notes + sources 포함)
        input_messages_tokens = 0  # HumanMessage, AIMessage 등 입력 메시지
        
        for msg in messages:
            msg_type = type(msg).__name__
            content = getattr(msg, "content", "")
            
            # 입력 메시지 (HumanMessage, AIMessage)
            if msg_type in ["HumanMessage", "AIMessage"]:
                if content:
                    input_messages_tokens += count_tokens(str(content))
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        input_messages_tokens += count_tokens(json.dumps(tc, ensure_ascii=False))
            
            # ToolMessage의 content에는 전체 데이터가 포함됨 (리서치 에이전트가 실제로 받는 데이터)
            if msg_type == "ToolMessage":
                tool_content = getattr(msg, "content", "")
                if tool_content:
                    tool_messages_full_tokens += count_tokens(tool_content)  # ToolMessage 전체
                    try:
                        tool_data = json.loads(tool_content)
                        if isinstance(tool_data, dict) and "data" in tool_data:
                            # 전체 데이터 배열의 토큰 수 계산
                            data_array = tool_data.get("data", [])
                            if data_array:
                                data_json = json.dumps(data_array, ensure_ascii=False)
                                tool_messages_data_tokens += count_tokens(data_json)
                    except:
                        pass
        
        # 리서치 에이전트가 출력하는 데이터
        research_notes = result_state.get("research_notes", "")
        notes_tokens = count_tokens(research_notes)
        
        research_sources = result_state.get("research_sources", [])
        sources_text = json.dumps(research_sources, ensure_ascii=False)
        sources_tokens = count_tokens(sources_text)
        
        research_payload = result_state.get("research_payload", [])
        payload_text = json.dumps(research_payload, ensure_ascii=False)
        payload_tokens = count_tokens(payload_text)
        
        # 리서치 에이전트의 최종 출력 (research_notes + research_sources)
        research_output_tokens = notes_tokens + sources_tokens
        
        # 리서치 에이전트가 처리한 전체 토큰 (입력 + 출력)
        research_total_tokens = input_messages_tokens + tool_messages_full_tokens + research_output_tokens
        
        print("=" * 80)
        print("📥 리서치 에이전트 입력 데이터")
        print("=" * 80)
        print(f"   - 입력 메시지 (HumanMessage, AIMessage): {input_messages_tokens:,} 토큰")
        print(f"   - ToolMessage 전체 (notes + sources + data): {tool_messages_full_tokens:,} 토큰")
        print(f"     └─ 그 중 데이터 배열 (50개 전체 + DESCRIPTION): {tool_messages_data_tokens:,} 토큰")
        print(f"   📊 입력 총합: {input_messages_tokens + tool_messages_full_tokens:,} 토큰")
        
        print("\n" + "=" * 80)
        print("📤 리서치 에이전트 출력 데이터")
        print("=" * 80)
        print(f"   - 연구 메모 (research_notes): {notes_tokens:,} 토큰")
        print(f"   - 참고 출처 (research_sources): {sources_tokens:,} 토큰")
        print(f"   - 데이터 페이로드 (research_payload): {payload_tokens:,} 토큰")
        print(f"   📊 출력 총합: {research_output_tokens:,} 토큰")
        
        print("\n" + "=" * 80)
        print("📊 리서치 에이전트 전체 처리 토큰 수")
        print("=" * 80)
        print(f"   입력: {input_messages_tokens + tool_messages_full_tokens:,} 토큰")
        print(f"   출력: {research_output_tokens:,} 토큰")
        print(f"   📊 총합: {research_total_tokens:,} 토큰")
        print(f"\n   ⚠️  리서치 에이전트는 ToolMessage로 전체 50개 데이터(+DESCRIPTION)를 받아서 요약합니다.")
        print(f"   ⚠️  분석 에이전트는 research_notes(요약)와 research_sources(URL 목록)만 받습니다.")
        
        print("\n[연구 메모]")
        print("-" * 80)
        print(result_state.get("research_notes", "없음"))
        
        print("\n[참고 출처]")
        print("-" * 80)
        sources = result_state.get("research_sources", [])
        if sources:
            for i, source in enumerate(sources[:10], 1):  # 최대 10개만 출력
                print(f"{i}. {source}")
            if len(sources) > 10:
                print(f"... 외 {len(sources) - 10}개")
        else:
            print("없음")
        
        print("\n[수집된 데이터 페이로드]")
        print("-" * 80)
        print("⚠️  주의: 이 데이터는 디버깅용으로만 표시됩니다.")
        print("⚠️  실제 분석 에이전트는 research_notes(텍스트 요약)와 research_sources(URL 목록)만 받습니다.")
        print("⚠️  research_payload의 샘플 데이터는 상태에 저장되지만 분석 에이전트에게는 전달되지 않습니다.\n")
        payloads = result_state.get("research_payload", [])
        if payloads:
            for i, payload in enumerate(payloads, 1):
                print(f"\n{i}. 도구: {payload.get('tool', 'N/A')}")
                print(f"   인자: {json.dumps(payload.get('args', {}), ensure_ascii=False, indent=2)}")
                print(f"   데이터 개수: {payload.get('count', 0)}")
                print(f"   ⚠️  실제 수집된 데이터: {payload.get('count', 0)}개 전체")
                print(f"   ⚠️  샘플 데이터 (research_payload에 저장된 것): 첫 5개만 (아래는 첫 1개)")
                if payload.get('sample'):
                    print(f"   샘플 데이터 (첫 1개):")
                    print(json.dumps(payload['sample'][0], ensure_ascii=False, indent=4))
        else:
            print("없음")
        
        print("\n[메시지 히스토리]")
        print("-" * 80)
        messages = result_state.get("messages", [])
        for i, msg in enumerate(messages, 1):
            msg_type = type(msg).__name__
            content = getattr(msg, "content", "")
            print(f"\n{i}. [{msg_type}]")
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                print(f"   도구 호출:")
                for tc in msg.tool_calls:
                    print(f"     - {tc.get('name', 'N/A')}: {json.dumps(tc.get('args', {}), ensure_ascii=False)}")
            if content:
                # 내용이 너무 길면 잘라서 출력
                content_str = str(content)[:500]
                if len(str(content)) > 500:
                    content_str += "... (생략)"
                print(f"   내용: {content_str}")
        
        print("\n" + "="*80)
        print("✅ 리서치 에이전트 실행 완료")
        print("="*80 + "\n")
        
    except Exception as e:
        print("\n" + "="*80)
        print("❌ 오류 발생")
        print("="*80)
        print(f"오류 메시지: {str(e)}")
        import traceback
        print("\n상세 오류:")
        traceback.print_exc()
        print("="*80 + "\n")


if __name__ == "__main__":
    main()
