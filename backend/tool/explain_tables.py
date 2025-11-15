"""테이블 차이 설명을 위한 스크립트"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from sqlalchemy import create_engine, text

engine = create_engine(settings.database_url)

print("=" * 80)
print("테이블 차이 설명")
print("=" * 80)

# facilities 테이블에서 기관명 확인
with engine.connect() as conn:
    # facilities에서 국립현대미술관 관련 시설 확인
    result = conn.execute(text("""
        SELECT DISTINCT cutr_facl_id, mrc_snbd_nm 
        FROM facilities 
        WHERE mrc_snbd_nm LIKE '%국립현대미술관%' 
        LIMIT 5
    """))
    print("\n[facilities 테이블 - 국립현대미술관 관련 시설]")
    for row in result:
        print(f"  cutr_facl_id: {row[0]}, 시설명: {row[1]}")
    
    # persona_metrics에서 해당 시설 데이터 확인
    result2 = conn.execute(text("""
        SELECT DISTINCT pm.cutr_facl_id, pm.cri_ym, f.mrc_snbd_nm
        FROM persona_metrics pm
        JOIN facilities f ON pm.cutr_facl_id = f.cutr_facl_id
        WHERE f.mrc_snbd_nm LIKE '%국립현대미술관%'
        LIMIT 5
    """))
    print("\n[persona_metrics 테이블 - 국립현대미술관 데이터]")
    for row in result2:
        print(f"  cutr_facl_id: {row[0]}, cri_ym: {row[1]}, 시설명: {row[2]}")
    
    # mrcno_demographics에서 해당 시설 데이터 확인
    result3 = conn.execute(text("""
        SELECT DISTINCT md.cutr_facl_id, md.cri_ym, f.mrc_snbd_nm
        FROM mrcno_demographics md
        JOIN facilities f ON md.cutr_facl_id = f.cutr_facl_id
        WHERE f.mrc_snbd_nm LIKE '%국립현대미술관%'
        LIMIT 5
    """))
    print("\n[mrcno_demographics 테이블 - 국립현대미술관 데이터]")
    for row in result3:
        print(f"  cutr_facl_id: {row[0]}, cri_ym: {row[1]}, 시설명: {row[2]}")

print("\n" + "=" * 80)
print("차이점:")
print("=" * 80)
print("1. persona_metrics: 문화시설 전체의 방문자 통계 (이미 집계됨)")
print("2. mrcno_demographics: 각 가맹점별 방문자 통계 (집계 필요)")
print("\n→ 페르소나(persona_metrics)만 사용하면 됩니다!")




