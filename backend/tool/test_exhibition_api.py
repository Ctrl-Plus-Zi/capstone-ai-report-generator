"""
전시정보 API 직접 테스트 스크립트
KCISA_CCA_145 API의 다양한 사용 방법을 테스트합니다.
"""
import sys
import os
from pathlib import Path

# Windows 콘솔 인코딩 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import dotenv
dotenv.load_dotenv()

from app.agents.api_utils import call_kcisa_api
import json
from datetime import datetime


def print_section(title: str, char: str = "="):
    """섹션 구분선 출력"""
    print(f"\n{char * 80}")
    print(f"{title}")
    print(f"{char * 80}\n")


def test_api_call(keyword=None, filter_value=None, num_of_rows=10, page_no=1):
    """API 호출 테스트"""
    print_section(f"[테스트] keyword={keyword}, filter_value={filter_value}, num_of_rows={num_of_rows}")
    
    result = call_kcisa_api(
        api_name="KCISA_CCA_145",
        keyword=keyword,
        filter_value=filter_value,
        num_of_rows=num_of_rows,
        page_no=page_no,
        filter_remove_fields=False
    )
    
    print(f"[성공 여부] {result.get('success', False)}")
    print(f"[데이터 개수] {result.get('count', 0)}")
    print(f"[호출 URL] {result.get('url', 'N/A')}")
    
    if result.get('error'):
        print(f"[오류] {result.get('error')}")
    
    if result.get('data'):
        print(f"\n[샘플 데이터] (최대 3개):")
        for i, item in enumerate(result['data'][:3], 1):
            print(f"\n  [{i}]")
            print(f"    - TITLE: {item.get('TITLE', 'N/A')}")
            print(f"    - CNTC_INSTT_NM: {item.get('CNTC_INSTT_NM', 'N/A')}")
            print(f"    - URL: {item.get('URL', 'N/A')}")
            print(f"    - PERIOD: {item.get('PERIOD', 'N/A')}")
            print(f"    - EVENT_PERIOD: {item.get('EVENT_PERIOD', 'N/A')}")
            print(f"    - IMAGE_OBJECT: {item.get('IMAGE_OBJECT', 'N/A')[:80] if item.get('IMAGE_OBJECT') else 'N/A'}")
            print(f"    - DESCRIPTION: {item.get('DESCRIPTION', 'N/A')[:100] if item.get('DESCRIPTION') else 'N/A'}...")
    
    return result


def main():
    print_section("전시정보 API 직접 테스트 스크립트", "=")
    print(f"[테스트 날짜] {datetime.now().strftime('%Y-%m-%d')}\n")
    
    # 테스트 케이스들
    test_cases = [
        {
            "name": "1. keyword='국립현대미술관' (서버 사이드 검색)",
            "keyword": "국립현대미술관",
            "filter_value": None,
            "num_of_rows": 10
        },
        {
            "name": "2. keyword='국립현대미술관', filter_value='www.mmca.go.kr' (둘 다 사용)",
            "keyword": "국립현대미술관",
            "filter_value": "www.mmca.go.kr",
            "num_of_rows": 10
        },
        {
            "name": "3. filter_value='www.mmca.go.kr' (클라이언트 사이드 필터만)",
            "keyword": None,
            "filter_value": "www.mmca.go.kr",
            "num_of_rows": 10
        },
    ]
    
    results = []
    
    for test_case in test_cases:
        print_section(test_case["name"], "-")
        result = test_api_call(
            keyword=test_case["keyword"],
            filter_value=test_case["filter_value"],
            num_of_rows=test_case["num_of_rows"]
        )
        results.append({
            "test_case": test_case["name"],
            "success": result.get("success", False),
            "count": result.get("count", 0),
            "keyword": test_case["keyword"],
            "filter_value": test_case["filter_value"]
        })
    
    # 결과 요약
    print_section("[테스트 결과 요약]", "=")
    print(f"{'테스트 케이스':<50} {'성공':<8} {'데이터 수':<10}")
    print("-" * 80)
    for r in results:
        status = "[OK]" if r["success"] else "[FAIL]"
        count = r["count"]
        print(f"{r['test_case']:<50} {status:<8} {count:<10}")
    
    # 가장 성공적인 케이스 찾기
    successful_cases = [r for r in results if r["success"] and r["count"] > 0]
    if successful_cases:
        print_section("[성공한 테스트 케이스]", "=")
        for r in successful_cases:
            print(f"\n{r['test_case']}")
            print(f"  - keyword: {r['keyword']}")
            print(f"  - filter_value: {r['filter_value']}")
            print(f"  - 데이터 수: {r['count']}")
    else:
        print_section("[모든 테스트 실패]", "=")
        print("API 호출이 성공하지 않았거나 데이터가 없습니다.")
        print("API 서버 상태나 파라미터를 확인해주세요.")


if __name__ == "__main__":
    main()

