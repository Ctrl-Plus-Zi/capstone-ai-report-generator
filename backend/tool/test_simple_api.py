"""간단한 API 테스트"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import dotenv
dotenv.load_dotenv()

from app.agents.api_utils import call_kcisa_api

# 테스트 1: keyword만 사용 (filter_value 없음)
print("=" * 80)
print("테스트 1: keyword='국립현대미술관', filter_value=None, num_of_rows=10")
print("=" * 80)
result1 = call_kcisa_api(
    api_name="KCISA_CCA_145",
    keyword="국립현대미술관",
    filter_value=None,
    num_of_rows=10
)
print(f"Success: {result1.get('success')}")
print(f"Count: {result1.get('count')}")
if result1.get('error'):
    print(f"Error: {result1.get('error')}")
print()

# 테스트 2: num_of_rows를 더 줄여서 테스트
print("=" * 80)
print("테스트 2: keyword='국립현대미술관', filter_value=None, num_of_rows=5")
print("=" * 80)
result2 = call_kcisa_api(
    api_name="KCISA_CCA_145",
    keyword="국립현대미술관",
    filter_value=None,
    num_of_rows=5
)
print(f"Success: {result2.get('success')}")
print(f"Count: {result2.get('count')}")
if result2.get('error'):
    print(f"Error: {result2.get('error')}")
print()

