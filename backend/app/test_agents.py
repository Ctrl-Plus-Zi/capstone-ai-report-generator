from __future__ import annotations
from pprint import pprint
from langchain_core.messages import HumanMessage
from agents.reporting_graph import ReportingGraph
import dotenv
import json

dotenv.load_dotenv()

def build_sample_state() -> dict:
    return {
        "request_context": {
            "organization_name": "국립중앙박물관",
            "report_topic": "2030 세대의 관람객 유입을 위한 이벤트 기획",
            "questions": [
                "국립중앙박물관의 최근 전시 정보를 조사해주세요.",
                "박물관의 대표 소장품(예: 청자, 불상)을 조사해주세요.",
                "2030 세대의 관람객 유입을 위한 이벤트 기획에 대해 분석해주세요.",
            ],
        },
        # Start the conversation with a single message to seed the context.
        "messages": [
            HumanMessage(content="""
국립중앙박물관의 보고서를 작성하기 위해 다음 정보를 조사해주세요:
1. 최근 전시 정보 (www.museum.go.kr 관련)
2. 대표 소장품 정보 (청자 관련)
3. 이를 바탕으로 2030 세대 유입을 위한 이벤트 기획 분석

조사 에이전트는 search_exhibition_info_api와 search_museum_collection_api 도구를 사용하여 
실제 데이터를 수집해주세요.
            """.strip())
        ],
    }


def run_demo() -> dict:
    print("=" * 80)
    print("🚀 보고서 자동화 파이프라인 테스트 시작")
    print("=" * 80)
    print()
    
    graph = ReportingGraph().graph
    initial_state = build_sample_state()
    
    print("📋 초기 요청 컨텍스트:")
    print(json.dumps(initial_state["request_context"], ensure_ascii=False, indent=2))
    print()
    print("-" * 80)
    print()
    
    print("⏳ 에이전트 실행 중...")
    print()
    
    result_state = graph.invoke(initial_state)
    
    print("=" * 80)
    print("✅ 파이프라인 실행 완료")
    print("=" * 80)
    print()
    
    # 주요 결과 출력
    print("📊 조사 메모:")
    print(result_state.get("research_notes", "없음"))
    print()
    print("-" * 80)
    print()
    
    print("🔍 참고 출처:")
    sources = result_state.get("research_sources", [])
    for i, source in enumerate(sources[:5], 1):  # 처음 5개만 출력
        print(f"{i}. {source}")
    if len(sources) > 5:
        print(f"... 외 {len(sources) - 5}개")
    print()
    print("-" * 80)
    print()
    
    print("📈 분석 결과:")
    print(result_state.get("analysis_findings", "없음"))
    print()
    print("-" * 80)
    print()
    
    print("📝 최종 보고서:")
    print(result_state.get("final_report", "없음"))
    print()
    print("=" * 80)
    
    return result_state


if __name__ == "__main__":
    try:
        result_state = run_demo()
        
        # 전체 결과를 파일로 저장
        with open("test_result.json", "w", encoding="utf-8") as f:
            # messages는 직렬화할 수 없으므로 제외
            output_state = {k: v for k, v in result_state.items() if k != "messages"}
            json.dump(output_state, f, ensure_ascii=False, indent=2, default=str)
        
        print()
        print("💾 전체 결과가 test_result.json에 저장되었습니다.")
        
    except Exception as e:
        print()
        print("❌ 오류 발생:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
