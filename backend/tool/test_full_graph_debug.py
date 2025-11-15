"""
전체 그래프 실행 디버깅 스크립트
리서치 에이전트, 분석 에이전트, 컴포즈 에이전트의 입력/출력 데이터를 모두 확인합니다.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import dotenv

# 프로젝트 루트를 Python 경로에 추가
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 환경 변수 로드
dotenv.load_dotenv()

from langchain_core.messages import HumanMessage
from app.agents.reporting_graph import ReportingGraph
from app.config import settings


def print_section(title: str, width: int = 100):
    """섹션 구분선 출력"""
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def print_data(title: str, data: Any, max_length: int = 2000):
    """데이터 출력 (길이 제한)"""
    print(f"\n[{title}]")
    print("-" * 100)
    if isinstance(data, dict):
        data_str = json.dumps(data, ensure_ascii=False, indent=2)
    elif isinstance(data, list):
        data_str = json.dumps(data, ensure_ascii=False, indent=2)
    elif isinstance(data, str):
        data_str = data
    else:
        data_str = str(data)
    
    if len(data_str) > max_length:
        print(data_str[:max_length])
        print(f"\n... (총 {len(data_str)}자, {max_length}자까지만 표시)")
    else:
        print(data_str)


def check_description_in_data(data: list, tool_name: str):
    """데이터에 DESCRIPTION 필드가 포함되어 있는지 확인"""
    if not data:
        return False, "데이터가 없습니다"
    
    has_description = False
    description_count = 0
    
    for item in data:
        if isinstance(item, dict):
            # 다양한 DESCRIPTION 필드명 확인
            desc_fields = ["DESCRIPTION", "description", "Description", "DESC", "desc"]
            for field in desc_fields:
                if field in item and item[field]:
                    has_description = True
                    description_count += 1
                    break
    
    return has_description, f"{description_count}/{len(data)}개 항목에 DESCRIPTION 포함"


def main():
    print_section("전체 그래프 실행 디버깅 스크립트")
    
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
    
    user_command = input("사용자 요청>> ").strip()
    if not user_command:
        print("❌ 사용자 요청을 입력해주세요.")
        return
    
    # 오늘 날짜 가져오기
    today = datetime.now()
    current_date = today.strftime("%Y-%m-%d")
    current_year = today.year
    current_month = today.month
    
    print(f"\n📅 오늘 날짜: {current_date}")
    
    # 초기 상태 생성
    initial_message = f"""
{organization_name}에 대한 보고서를 작성해주세요.

사용자 요청:
{user_command}

오늘 날짜: {current_date}
현재 진행 중인 공연/전시만 포함해주세요.

위 요청을 바탕으로 필요한 데이터를 수집하고 분석하여 전문적인 보고서를 작성하세요.
""".strip()

    initial_state = {
        "request_context": {
            "organization_name": organization_name,
            "report_topic": user_command,
            "questions": [user_command],
            "current_date": current_date,
            "current_year": current_year,
            "current_month": current_month,
            "filter_active_only": True,
        },
        "messages": [HumanMessage(content=initial_message)],
    }
    
    print_section("초기 상태")
    print_data("Request Context", initial_state["request_context"])
    print_data("Initial Message", initial_state["messages"][0].content)
    
    # 그래프 초기화
    print_section("그래프 초기화 중...")
    try:
        graph_instance = ReportingGraph()
        graph = graph_instance.graph
        print("✅ 그래프 초기화 완료")
    except Exception as e:
        print(f"❌ 그래프 초기화 실패: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 그래프 실행
    print_section("그래프 실행 시작")
    
    # 각 노드의 입력/출력을 저장할 딕셔너리
    node_debug_data = {
        "research_agent": {
            "input": None,
            "output": None,
        },
        "analysis_agent": {
            "input": None,
            "output": None,
        },
        "compose_agent": {
            "input": None,
            "output": None,
        }
    }
    
    try:
        # 그래프를 스트림으로 실행하여 각 노드의 출력을 캡처
        print("그래프를 스트림 모드로 실행하여 각 노드의 입력/출력을 캡처합니다...")
        
        # 각 노드 실행 전후 상태를 저장
        states = {}
        current_state = initial_state.copy()
        
        # 그래프 스트림 실행
        for event in graph.stream(initial_state):
            # 이벤트는 {노드명: 출력} 형태
            for node_name, node_output in event.items():
                if node_name == "Research Agent":
                    print_section("1. Research Agent 실행 완료")
                    states["research_agent_input"] = current_state.copy()
                    states["research_agent_output"] = node_output.copy()
                    node_debug_data["research_agent"]["input"] = {
                        "request_context": current_state.get("request_context"),
                        "messages_count": len(current_state.get("messages", [])),
                    }
                    node_debug_data["research_agent"]["output"] = {
                        "research_notes": node_output.get("research_notes", ""),
                        "research_sources": node_output.get("research_sources", []),
                        "research_payload": node_output.get("research_payload", []),
                        "messages_count": len(node_output.get("messages", [])),
                    }
                    current_state.update(node_output)
                    
                    # Research Agent 출력 확인
                    print_data("research_notes", node_output.get("research_notes", ""))
                    print_data("research_sources", node_output.get("research_sources", []))
                    
                    research_payload = node_output.get("research_payload", [])
                    print_data("research_payload (수집된 데이터 샘플)", research_payload)
                    
                    # DESCRIPTION 포함 여부 확인
                    print_section("API 데이터 DESCRIPTION 포함 여부 확인")
                    for payload in research_payload:
                        tool_name = payload.get("tool", "N/A")
                        sample_data = payload.get("sample", [])
                        if sample_data:
                            has_desc, desc_info = check_description_in_data(sample_data, tool_name)
                            print(f"\n[{tool_name}]")
                            print(f"  DESCRIPTION 포함 여부: {'✅ 포함됨' if has_desc else '❌ 포함되지 않음'}")
                            print(f"  상세: {desc_info}")
                            if has_desc and sample_data:
                                # DESCRIPTION이 있는 첫 번째 항목 출력
                                first_item = sample_data[0]
                                desc_fields = ["DESCRIPTION", "description", "Description", "DESC", "desc"]
                                for field in desc_fields:
                                    if field in first_item:
                                        desc_value = first_item[field]
                                        if desc_value:
                                            desc_preview = desc_value[:200] if len(desc_value) > 200 else desc_value
                                            print(f"  {field} 샘플: {desc_preview}...")
                                        break
                
                elif node_name == "Analysis Agent":
                    print_section("2. Analysis Agent 실행 완료")
                    states["analysis_agent_input"] = current_state.copy()
                    states["analysis_agent_output"] = node_output.copy()
                    node_debug_data["analysis_agent"]["input"] = {
                        "request_context": current_state.get("request_context"),
                        "research_notes": current_state.get("research_notes", ""),
                        "research_sources": current_state.get("research_sources", []),
                        "messages_count": len(current_state.get("messages", [])),
                    }
                    node_debug_data["analysis_agent"]["output"] = {
                        "analysis_outline": node_output.get("analysis_outline", ""),
                        "analysis_findings": node_output.get("analysis_findings", ""),
                        "messages_count": len(node_output.get("messages", [])),
                    }
                    current_state.update(node_output)
                    
                    # Analysis Agent 입력/출력 확인
                    print_section("Analysis Agent 입력 데이터")
                    print_data("받은 research_notes", current_state.get("research_notes", ""))
                    print_data("받은 research_sources", current_state.get("research_sources", []))
                    
                    print_section("Analysis Agent 출력 데이터")
                    print_data("analysis_outline", node_output.get("analysis_outline", ""))
                    print_data("analysis_findings", node_output.get("analysis_findings", ""))
                
                elif node_name == "Compose Agent":
                    print_section("3. Compose Agent 실행 완료")
                    states["compose_agent_input"] = current_state.copy()
                    states["compose_agent_output"] = node_output.copy()
                    node_debug_data["compose_agent"]["input"] = {
                        "request_context": current_state.get("request_context"),
                        "analysis_outline": current_state.get("analysis_outline", ""),
                        "analysis_findings": current_state.get("analysis_findings", ""),
                        "research_notes": current_state.get("research_notes", ""),
                    }
                    node_debug_data["compose_agent"]["output"] = {
                        "final_report": node_output.get("final_report", ""),
                        "compose_prompt": node_output.get("compose_prompt", ""),
                    }
                    
                    # Compose Agent 입력/출력 확인
                    print_section("Compose Agent 입력 데이터")
                    print_data("받은 request_context", current_state.get("request_context"))
                    print_data("받은 analysis_outline", current_state.get("analysis_outline", ""))
                    print_data("받은 analysis_findings", current_state.get("analysis_findings", ""))
                    print_data("받은 research_notes", current_state.get("research_notes", ""))
                    
                    print_section("Compose Agent 출력 데이터")
                    print_data("final_report", node_output.get("final_report", ""))
                    print_data("compose_prompt (사용된 프롬프트)", node_output.get("compose_prompt", ""), max_length=5000)
        
        # 최종 요약
        print_section("최종 요약")
        print("\n[데이터 흐름 요약]")
        print("-" * 100)
        
        research_output = states.get("research_agent_output", {})
        analysis_input = states.get("analysis_agent_input", {})
        analysis_output = states.get("analysis_agent_output", {})
        compose_input = states.get("compose_agent_input", {})
        compose_output = states.get("compose_agent_output", {})
        
        print("1. Research Agent:")
        print(f"   - 입력: 초기 요청 (기관명: {organization_name}, 요청: {user_command})")
        print(f"   - 출력: research_notes ({len(research_output.get('research_notes', ''))}자), "
              f"research_sources ({len(research_output.get('research_sources', []))}개)")
        
        print("\n2. Analysis Agent:")
        print(f"   - 입력: research_notes ({len(analysis_input.get('research_notes', ''))}자), "
              f"research_sources ({len(analysis_input.get('research_sources', []))}개)")
        print(f"   - 출력: analysis_outline ({len(analysis_output.get('analysis_outline', ''))}자), "
              f"analysis_findings ({len(analysis_output.get('analysis_findings', ''))}자)")
        
        print("\n3. Compose Agent:")
        print(f"   - 입력: analysis_outline ({len(compose_input.get('analysis_outline', ''))}자), "
              f"analysis_findings ({len(compose_input.get('analysis_findings', ''))}자), "
              f"research_notes ({len(compose_input.get('research_notes', ''))}자)")
        print(f"   - 출력: final_report ({len(compose_output.get('final_report', ''))}자)")
        
        # 디버그 데이터를 JSON 파일로 저장
        debug_file = Path(__file__).parent / f"debug_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(debug_file, "w", encoding="utf-8") as f:
            json.dump(node_debug_data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 디버그 데이터가 저장되었습니다: {debug_file}")
        
        print_section("✅ 전체 그래프 실행 완료")
        
    except Exception as e:
        print_section("❌ 오류 발생")
        print(f"오류 메시지: {str(e)}")
        import traceback
        print("\n상세 오류:")
        traceback.print_exc()
        
        # 오류 발생 시까지의 디버그 데이터 저장
        debug_file = Path(__file__).parent / f"debug_output_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(debug_file, "w", encoding="utf-8") as f:
            json.dump(node_debug_data, f, ensure_ascii=False, indent=2)
        print(f"\n⚠️  오류 발생 시점까지의 디버그 데이터가 저장되었습니다: {debug_file}")


if __name__ == "__main__":
    main()

