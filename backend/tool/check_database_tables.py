"""데이터베이스 테이블 확인"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from sqlalchemy import create_engine, inspect, text

print(f"데이터베이스 연결: {settings.database_url}")

engine = create_engine(settings.database_url, pool_pre_ping=True)

inspector = inspect(engine)
tables = inspector.get_table_names()

print(f"\n테이블 목록 ({len(tables)}개):")
for table in tables:
    print(f"  - {table}")
    columns = inspector.get_columns(table)
    print(f"    컬럼 수: {len(columns)}")
    if len(columns) <= 10:
        print(f"    컬럼: {[c['name'] for c in columns]}")

# 스텔라큐브 관련 테이블 찾기
print("\n스텔라큐브 관련 테이블 검색:")
for table in tables:
    if any(keyword in table.lower() for keyword in ['stellarcube', 'sscard', 'mrcno', 'persona', 'facility', '문화시설']):
        print(f"\n  테이블: {table}")
        columns = inspector.get_columns(table)
        print(f"  컬럼:")
        for col in columns[:20]:  # 처음 20개만
            print(f"    - {col['name']} ({col['type']})")

