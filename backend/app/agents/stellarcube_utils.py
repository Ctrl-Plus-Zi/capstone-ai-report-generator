"""
스텔라큐브 데이터 조회 유틸리티
AWS RDS에서 월별 연령대 비율 데이터를 조회합니다.
"""
from typing import Dict, List, Optional, Any
from sqlalchemy import create_engine, text
from app.config import settings
from app.db.session import SessionLocal


# 기관명 매핑
ORGANIZATION_MAPPING = {
    "국립현대미술관": "국립현대미술관서울관",
    "국립중앙박물관": "국립중앙박물관",
    "예술의전당": "예술의전당한가람미술관",
    "예술의 전당": "예술의전당한가람미술관",
}


def get_organization_name_for_query(org_name: str) -> str:
    """기관명을 데이터베이스 조회용 이름으로 변환"""
    return ORGANIZATION_MAPPING.get(org_name, org_name)


def get_monthly_age_gender_ratio(
    organization_name: str,
    year: Optional[int] = None,
    month: Optional[int] = None
) -> Dict[str, Any]:
    """
    월별 남성/여성 연령대 비율 데이터 조회
    
    Args:
        organization_name: 기관명
        year: 조회할 연도 (None이면 전체)
        month: 조회할 월 (None이면 전체)
    
    Returns:
        {
            "success": bool,
            "data": [
                {
                    "cri_ym": "202408",
                    "male_20s": 0.03,
                    "male_30s": 0.093,
                    "male_40s": 0.135,
                    "male_50s": 0.024,
                    "male_60s": 0.002,
                    "male_70s": 0.0,
                    "female_20s": 0.011,
                    "female_30s": 0.092,
                    "female_40s": 0.053,
                    "female_50s": 0.047,
                    "female_60s": 0.0,
                    "female_70s": 0.0,
                },
                ...
            ],
            "organization_name": str,
            "error": str (if failed)
        }
    """
    try:
        db_org_name = get_organization_name_for_query(organization_name)
        
        # 데이터베이스 연결
        db = SessionLocal()
        try:
            # persona_metrics 테이블 사용 (문화시설 전체의 방문자 통계)
            # facilities 테이블과 조인하여 기관명으로 필터링
            base_query = """
                SELECT 
                    pm.cri_ym,
                    AVG(pm.persona_pct_20_male) as male_20s,
                    AVG(pm.persona_pct_30_male) as male_30s,
                    AVG(pm.persona_pct_40_male) as male_40s,
                    AVG(pm.persona_pct_50_male) as male_50s,
                    AVG(pm.persona_pct_60_male) as male_60s,
                    AVG(pm.persona_pct_70_male) as male_70s,
                    AVG(pm.persona_pct_20_female) as female_20s,
                    AVG(pm.persona_pct_30_female) as female_30s,
                    AVG(pm.persona_pct_40_female) as female_40s,
                    AVG(pm.persona_pct_50_female) as female_50s,
                    AVG(pm.persona_pct_60_female) as female_60s,
                    AVG(pm.persona_pct_70_female) as female_70s
                FROM persona_metrics pm
                JOIN facilities f ON pm.cutr_facl_id = f.cutr_facl_id
                WHERE f.mrc_snbd_nm LIKE :org_pattern
            """
            
            # WHERE 조건 추가
            params = {"org_pattern": f"%{db_org_name}%"}
            
            if year:
                if month:
                    # 특정 년월 (예: 2025년 1월 -> cri_ym = 202501)
                    params["year_pattern"] = int(f"{year}{month:02d}")
                    query = text(base_query + """
                        AND pm.cri_ym = :year_pattern
                        GROUP BY pm.cri_ym
                        ORDER BY pm.cri_ym
                    """)
                else:
                    # 특정 년도 전체
                    params["year_pattern"] = f"{year}%"
                    query = text(base_query + """
                        AND pm.cri_ym::text LIKE :year_pattern
                        GROUP BY pm.cri_ym
                        ORDER BY pm.cri_ym
                    """)
            else:
                # 전체 기간
                query = text(base_query + """
                    GROUP BY pm.cri_ym
                    ORDER BY pm.cri_ym
                """)
            
            result = db.execute(query, params)
            rows = result.fetchall()
            
            data = []
            for row in rows:
                # cri_ym이 INTEGER이므로 문자열로 변환 (예: 202408 -> "202408")
                cri_ym_str = str(row.cri_ym)
                data.append({
                    "cri_ym": cri_ym_str,
                    "male_20s": float(row.male_20s or 0),
                    "male_30s": float(row.male_30s or 0),
                    "male_40s": float(row.male_40s or 0),
                    "male_50s": float(row.male_50s or 0),
                    "male_60s": float(row.male_60s or 0),
                    "male_70s": float(row.male_70s or 0),
                    "female_20s": float(row.female_20s or 0),
                    "female_30s": float(row.female_30s or 0),
                    "female_40s": float(row.female_40s or 0),
                    "female_50s": float(row.female_50s or 0),
                    "female_60s": float(row.female_60s or 0),
                    "female_70s": float(row.female_70s or 0),
                })
            
            return {
                "success": True,
                "data": data,
                "organization_name": organization_name,
                "db_organization_name": db_org_name,
                "count": len(data)
            }
            
        finally:
            db.close()
            
    except Exception as e:
        return {
            "success": False,
            "data": [],
            "organization_name": organization_name,
            "error": str(e),
            "count": 0
        }

