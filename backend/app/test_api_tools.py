from agents.graph_util import ReportingTools
from pprint import pprint
import json


def test_exhibition_info_api():
    """전시정보 API 테스트"""
    print("=" * 80)
    print("전시정보 API 테스트 (KCISA_CCA_145)")
    print("=" * 80)
    print()
    
    toolkit = ReportingTools()
    
    # 국립중앙박물관 전시 정보 검색
    print("검색 키워드: www.museum.go.kr")
    print("API 호출 중...")
    result = toolkit.search_exhibition_info_api.invoke({
        "keyword": "www.museum.go.kr",
        "num_of_rows": 10
    })
    
    print()
    print("결과:")
    print(f"메모: {result.get('notes', '')}")
    print(f"데이터 개수: {len(result.get('data', []))}개")
    print(f"참고 출처: {len(result.get('sources', []))}개")
    print()
    print("데이터 샘플 (처음 2개):")
    for i, item in enumerate(result.get('data', [])[:2], 1):
        print(f"\n[{i}]")
        print(f"  제목: {item.get('TITLE', 'N/A')}")
        print(f"  기관: {item.get('CNTC_INSTT_NM', 'N/A')}")
        print(f"  기간: {item.get('PERIOD', 'N/A')}")
        print(f"  URL: {item.get('URL', 'N/A')}")
    print()
    
    return result


def test_museum_collection_api():
    """소장품 검색 API 테스트"""
    print("=" * 80)
    print("소장품 검색 API 테스트 (KCISA_CPM_003)")
    print("=" * 80)
    print()
    
    toolkit = ReportingTools()
    
    # 청자 관련 소장품 검색
    print("검색 키워드: 청자")
    print("API 호출 중...")
    result = toolkit.search_museum_collection_api.invoke({
        "keyword": "청자",
        "num_of_rows": 10
    })
    
    print()
    print("결과:")
    print(f"메모: {result.get('notes', '')}")
    print(f"데이터 개수: {len(result.get('data', []))}개")
    print(f"참고 출처: {len(result.get('sources', []))}개")
    print()
    print("데이터 샘플 (처음 2개):")
    for i, item in enumerate(result.get('data', [])[:2], 1):
        print(f"\n[{i}]")
        print(f"  명칭: {item.get('title', 'N/A')}")
        print(f"  제작연대: {item.get('issuedDate', 'N/A')}")
        print(f"  크기: {item.get('sizing', 'N/A')}")
        print(f"  URL: {item.get('url', 'N/A')}")
    print()
    
    return result


def test_all_apis():
    """모든 API 테스트"""
    print("\n" + "=" * 75)
    print("   API 툴 통합 테스트 시작")
    print("=" * 75 + "\n")
    
    results = {}
    
    try:
        # 1. 전시정보 API 테스트
        results["exhibition"] = test_exhibition_info_api()
        print()
        
        # 2. 소장품 검색 API 테스트
        results["collection"] = test_museum_collection_api()
        print()
        
        # 결과 요약
        print("=" * 80)
        print("테스트 결과 요약")
        print("=" * 80)
        print()
        
        exhibition_data = results["exhibition"].get("data", [])
        if exhibition_data or results["exhibition"].get("notes"):
            print(f"전시정보 API: {len(exhibition_data)}개 검색 성공")
            print(f"   참고 출처: {len(results['exhibition'].get('sources', []))}개")
        else:
            print(f"전시정보 API: 실패")
        print()
        
        collection_data = results["collection"].get("data", [])
        if collection_data or results["collection"].get("notes"):
            print(f"소장품 API: {len(collection_data)}개 검색 성공")
            print(f"   참고 출처: {len(results['collection'].get('sources', []))}개")
        else:
            print(f"소장품 API: 실패")
        print()
        
        # 결과를 파일로 저장
        with open("test_api_tools_result.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        print("전체 결과가 test_api_tools_result.json에 저장되었습니다.")
        print()
        
        return results
        
    except Exception as e:
        print()
        print("오류 발생:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    test_all_apis()

