"""
국립현대미술관 전시 정보 API 테스트 스크립트
API가 호출되지 않는 이유를 찾기 위한 디버깅 스크립트
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import time
from app.agents.graph_util import ReportingTools
from app.config import settings
import dotenv

dotenv.load_dotenv()


def print_section(title: str, content: any = None):
    """섹션 출력 헬퍼"""
    print("\n" + "="*80)
    print(f"[섹션] {title}")
    print("="*80)
    if content is not None:
        if isinstance(content, dict):
            print(json.dumps(content, ensure_ascii=False, indent=2))
        elif isinstance(content, list):
            for i, item in enumerate(content, 1):
                if isinstance(item, dict):
                    print(f"\n[{i}] {json.dumps(item, ensure_ascii=False)[:200]}...")
                else:
                    print(f"[{i}] {item}")
        else:
            print(content)
    print("="*80)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="국립현대미술관 전시 정보 API 테스트")
    parser.add_argument("--keyword", type=str, default="국립현대미술관", help="검색 키워드 (기본값: 국립현대미술관)")
    parser.add_argument("--num-of-rows", type=int, default=50, help="조회할 행 수 (기본값: 50)")
    parser.add_argument("--timeout", type=int, default=30, help="Read 타임아웃 (초) (기본값: 30)")
    parser.add_argument("--connect-timeout", type=int, default=10, help="Connect 타임아웃 (초) (기본값: 10)")
    parser.add_argument("--no-keyword", action="store_true", help="키워드 없이 전체 조회 테스트")
    parser.add_argument("--show-url", action="store_true", help="실제 요청 URL 출력")
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("[테스트] 국립현대미술관 전시 정보 API 테스트")
    print("="*80)
    
    # 테스트 파라미터
    keyword = None if args.no_keyword else args.keyword
    num_of_rows = args.num_of_rows
    read_timeout = args.timeout
    connect_timeout = args.connect_timeout
    
    print(f"\n[파라미터] 테스트 파라미터:")
    print(f"  - 키워드: {keyword if keyword else '(없음 - 전체 조회)'}")
    print(f"  - 행 수: {num_of_rows}")
    print(f"  - Connect 타임아웃: {connect_timeout}초")
    print(f"  - Read 타임아웃: {read_timeout}초")
    
    # 툴킷 초기화
    print("\n[1/3] ReportingTools 초기화...")
    toolkit = ReportingTools()
    print("  [OK] 툴킷 초기화 완료")
    
    # API 직접 호출 (타임아웃 설정 가능하도록)
    print("\n[2/3] search_exhibition_info_api 호출...")
    print(f"  - 키워드: {keyword if keyword else '(없음)'}")
    print(f"  - 행 수: {num_of_rows}")
    
    # api_utils를 직접 사용하여 타임아웃 설정 가능하게
    from app.agents import api_utils
    
    start_time = time.time()
    try:
        # api_utils.call_kcisa_api 직접 호출
        result = api_utils.call_kcisa_api(
            api_name="KCISA_CCA_145",
            keyword=keyword,
            num_of_rows=num_of_rows,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )
        
        # 결과를 toolkit 형식으로 변환
        if result["success"]:
            formatted_result = {
                "notes": f"{result.get('api_description', '전시 정보')} 검색 완료: 총 {result['count']}개의 전시 정보를 찾았습니다.",
                "sources": [item.get("URL") for item in result["data"] if item.get("URL")],
                "data": result["data"],
                "count": result["count"],
                "url": result.get("url"),  # URL 포함
            }
        else:
            formatted_result = {
                "notes": f"전시 정보 검색 실패: {result.get('error', '알 수 없는 오류')}",
                "sources": [],
                "data": [],
                "count": 0,
                "url": result.get("url"),  # URL 포함
            }
        
        result = formatted_result
        
        # 실제 요청 URL 출력
        if args.show_url and result.get("url"):
            print(f"\n[URL] 실제 요청 URL:")
            print(f"  {result['url']}")
        elapsed_time = time.time() - start_time
        
        print(f"\n[3/3] API 호출 완료 (소요 시간: {elapsed_time:.2f}초)")
        
        if isinstance(result, dict):
            print_section("API 호출 결과", result)
            
            # 상세 분석
            notes = result.get("notes", "")
            data = result.get("data", [])
            sources = result.get("sources", [])
            count = result.get("count", 0)
            
            print(f"\n[분석] 결과 분석:")
            print(f"  - 메모: {notes}")
            print(f"  - 데이터 개수: {len(data)}")
            print(f"  - count 필드: {count}")
            print(f"  - 출처 개수: {len(sources)}")
            
            if data:
                print(f"\n[샘플] 데이터 샘플 (최대 5개):")
                for i, item in enumerate(data[:5], 1):
                    print(f"\n  [{i}] {json.dumps(item, ensure_ascii=False, indent=2)[:500]}...")
                
                # 필드 확인
                if data:
                    first_item = data[0]
                    print(f"\n[필드] 첫 번째 데이터 필드:")
                    for key in first_item.keys():
                        value = first_item[key]
                        value_str = str(value)[:100] if value else "None"
                        print(f"  - {key}: {value_str}")
            else:
                print("\n[경고] 데이터가 비어있습니다!")
                print("  - API 호출은 성공했지만 데이터가 반환되지 않았습니다.")
                print("  - 가능한 원인:")
                print("    1. 키워드 매칭 실패")
                print("    2. 필터 조건에 맞는 데이터 없음")
                print("    3. API 응답 형식 변경")
        else:
            print_section("API 호출 결과 (비정상)", {"type": type(result).__name__, "result": str(result)[:500]})
            
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"\n[에러] API 호출 실패 (소요 시간: {elapsed_time:.2f}초)")
        print(f"\n에러 타입: {type(e).__name__}")
        print(f"에러 메시지: {str(e)}")
        import traceback
        print(f"\n상세 스택 트레이스:")
        traceback.print_exc()
        
        print("\n" + "="*80)
        print("[원인 분석] 에러 원인 분석")
        print("="*80)
        print("가능한 원인:")
        print("  1. API 키 설정 문제 (.env 파일 확인)")
        print("  2. 네트워크 연결 문제")
        print("  3. API 엔드포인트 변경")
        print("  4. 타임아웃 설정 문제")
        print("="*80)
    
    print("\n" + "="*80)
    print("[완료] 테스트 완료")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
