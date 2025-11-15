"""
mrcno_demographics를 사용하여 기관별 유동인구 파악 가능 여부 확인
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from sqlalchemy import create_engine, text

engine = create_engine(settings.database_url)

print("=" * 80)
print("mrcno_demographics로 기관별 유동인구 파악 가능 여부 확인")
print("=" * 80)

with engine.connect() as conn:
    # 1. facilities에서 국립현대미술관 관련 시설 확인
    print("\n[1] facilities 테이블 - 국립현대미술관 관련 시설:")
    result1 = conn.execute(text("""
        SELECT cutr_facl_id, mrc_snbd_nm, COUNT(*) as facility_count
        FROM facilities 
        WHERE mrc_snbd_nm LIKE '%국립현대미술관%'
        GROUP BY cutr_facl_id, mrc_snbd_nm
        LIMIT 10
    """))
    facilities = []
    for row in result1:
        print(f"  cutr_facl_id: {row[0]}, 시설명: {row[1]}")
        facilities.append(row[0])
    
    if facilities:
        # 2. mrcno_demographics에서 해당 시설들의 데이터 확인
        print(f"\n[2] mrcno_demographics 테이블 - cutr_facl_id {facilities[0]} 데이터:")
        result2 = conn.execute(text("""
            SELECT 
                cri_ym,
                COUNT(*) as record_count,
                AVG(mrcno_pct_20_male) as avg_male_20s,
                AVG(mrcno_pct_30_male) as avg_male_30s,
                SUM(mrcno_pct_20_male + mrcno_pct_30_male + mrcno_pct_40_male + 
                    mrcno_pct_50_male + mrcno_pct_60_male + mrcno_pct_70_male +
                    mrcno_pct_20_female + mrcno_pct_30_female + mrcno_pct_40_female +
                    mrcno_pct_50_female + mrcno_pct_60_female + mrcno_pct_70_female) as total_ratio_sum
            FROM mrcno_demographics
            WHERE cutr_facl_id = :facility_id
            GROUP BY cri_ym
            ORDER BY cri_ym
            LIMIT 5
        """), {"facility_id": facilities[0]})
        
        for row in result2:
            print(f"  cri_ym: {row[0]}, 레코드 수: {row[1]}, 평균 남성 20대: {row[2] or 0:.4f}, 평균 남성 30대: {row[3] or 0:.4f}, 비율 합계: {row[4] or 0:.4f}")
        
        # 3. 같은 cutr_facl_id를 가진 여러 가맹점이 있는지 확인
        print(f"\n[3] 같은 cutr_facl_id를 가진 가맹점 수 확인:")
        result3 = conn.execute(text("""
            SELECT 
                md.cutr_facl_id,
                f.mrc_snbd_nm,
                COUNT(DISTINCT md.id) as record_count,
                md.cri_ym
            FROM mrcno_demographics md
            JOIN facilities f ON md.cutr_facl_id = f.cutr_facl_id
            WHERE f.mrc_snbd_nm LIKE '%국립현대미술관%'
            GROUP BY md.cutr_facl_id, f.mrc_snbd_nm, md.cri_ym
            ORDER BY md.cutr_facl_id, md.cri_ym
            LIMIT 10
        """))
        
        for row in result3:
            print(f"  cutr_facl_id: {row[0]}, 시설명: {row[1]}, 레코드 수: {row[2]}, cri_ym: {row[3]}")
        
        # 4. 기관별로 집계했을 때 데이터 확인
        print(f"\n[4] 기관별 집계 (국립현대미술관 전체):")
        result4 = conn.execute(text("""
            SELECT 
                md.cri_ym,
                COUNT(DISTINCT md.cutr_facl_id) as facility_count,
                COUNT(*) as total_records,
                AVG(md.mrcno_pct_20_male) as avg_male_20s,
                AVG(md.mrcno_pct_30_male) as avg_male_30s,
                AVG(md.mrcno_pct_40_male) as avg_male_40s,
                AVG(md.mrcno_pct_20_female) as avg_female_20s,
                AVG(md.mrcno_pct_30_female) as avg_female_30s
            FROM mrcno_demographics md
            JOIN facilities f ON md.cutr_facl_id = f.cutr_facl_id
            WHERE f.mrc_snbd_nm LIKE '%국립현대미술관%'
            GROUP BY md.cri_ym
            ORDER BY md.cri_ym
            LIMIT 5
        """))
        
        for row in result4:
            print(f"  cri_ym: {row[0]}, 시설 수: {row[1]}, 총 레코드: {row[2]}, 평균 남성 20대: {row[3] or 0:.4f}, 평균 남성 30대: {row[4] or 0:.4f}, 평균 남성 40대: {row[5] or 0:.4f}, 평균 여성 20대: {row[6] or 0:.4f}, 평균 여성 30대: {row[7] or 0:.4f}")

print("\n" + "=" * 80)
print("결론:")
print("=" * 80)
print("mrcno_demographics는 가맹점별 데이터이므로,")
print("같은 기관(cutr_facl_id 또는 mrc_snbd_nm으로 그룹화)의 데이터를 집계하면")
print("기관별 유동인구 비율을 파악할 수 있습니다.")
print("\n하지만 실제 유동인구 '수'는 비율만으로는 알 수 없고,")
print("비율 데이터만 제공됩니다.")

