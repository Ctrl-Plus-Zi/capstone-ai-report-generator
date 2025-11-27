"""
구글맵 리뷰 평점 통계 조회 유틸리티
AWS RDS capstone DB에서 구글맵 리뷰 데이터를 조회하여 평점 통계를 계산합니다.
"""
from typing import Dict, Any, Optional
from sqlalchemy import create_engine, text
from app.config import settings
from app.db.session import CapstoneSessionLocal


# 기관명 → 시설명 매핑 (google_map_facilities.slta_nm과 매칭)
# facilities.mrc_snbd_nm과 google_map_facilities.slta_nm을 매칭하거나
# cutr_facl_id로 연결할 수 있지만, 일단 시설명으로 매칭
GOOGLE_MAP_ORG_MAPPING = {
    "국립현대미술관": "국립현대미술관",
    "국립중앙박물관": "국립중앙박물관",
    "예술의전당": "예술의전당",
    "예술의 전당": "예술의전당",
    # 추가 기관명 매핑 필요시 여기에 추가
}


def get_google_map_rating_statistics(
    organization_name: str
) -> Dict[str, Any]:
    """
    구글맵 리뷰 평점 통계 조회
    
    Args:
        organization_name: 기관명
    
    Returns:
        {
            "success": bool,
            "data": {
                "total_reviews": 1234,
                "average_rating": 4.5,
                "rating_distribution": {
                    "5": 500,
                    "4": 400,
                    "3": 200,
                    "2": 100,
                    "1": 34
                },
                "rating_percentages": {
                    "5": 40.5,
                    "4": 32.4,
                    "3": 16.2,
                    "2": 8.1,
                    "1": 2.8
                }
            },
            "organization_name": str,
            "error": str (if failed)
        }
    """
    try:
        # 기관명을 시설명으로 변환 (필요시)
        facility_name = GOOGLE_MAP_ORG_MAPPING.get(organization_name, organization_name)
        
        # capstone DB 연결 (팀원 데이터)
        db = CapstoneSessionLocal()
        try:
            # sns_buzz_master_tbl과 sns_buzz_extract_contents를 조인하여 평점 통계 계산
            # 기관명 매칭: facilities.mrc_snbd_nm과 sns_buzz_master_tbl.slta_nm을 유사도 기반으로 검색
            # LIKE 패턴 매칭을 사용하여 기관명이 정확히 일치하지 않아도 유사한 시설을 찾을 수 있음
            query = text("""
                SELECT 
                    COUNT(*) as total_reviews,
                    AVG(gmr.sns_content_rating) as average_rating,
                    COUNT(CASE WHEN gmr.sns_content_rating = 5 THEN 1 END) as rating_5,
                    COUNT(CASE WHEN gmr.sns_content_rating = 4 THEN 1 END) as rating_4,
                    COUNT(CASE WHEN gmr.sns_content_rating = 3 THEN 1 END) as rating_3,
                    COUNT(CASE WHEN gmr.sns_content_rating = 2 THEN 1 END) as rating_2,
                    COUNT(CASE WHEN gmr.sns_content_rating = 1 THEN 1 END) as rating_1
                FROM sns_buzz_extract_contents gmr
                JOIN sns_buzz_master_tbl gmf ON gmr.slta_cd = gmf.slta_cd
                LEFT JOIN facilities f ON f.mrc_snbd_nm LIKE gmf.slta_nm
                WHERE gmr.sns_type = 'googlemap'
                    AND gmr.sns_content_rating IS NOT NULL
                    AND (
                        f.mrc_snbd_nm LIKE :org_pattern
                        OR gmf.slta_nm LIKE :org_pattern
                    )
            """)
            
            # 유사도 기반 검색: 기관명이 포함된 모든 시설 검색
            params = {"org_pattern": f"%{facility_name}%"}
            
            result = db.execute(query, params)
            row = result.fetchone()
            
            if not row or row.total_reviews == 0:
                return {
                    "success": True,
                    "data": {
                        "total_reviews": 0,
                        "average_rating": 0.0,
                        "rating_distribution": {
                            "5": 0,
                            "4": 0,
                            "3": 0,
                            "2": 0,
                            "1": 0
                        },
                        "rating_percentages": {
                            "5": 0.0,
                            "4": 0.0,
                            "3": 0.0,
                            "2": 0.0,
                            "1": 0.0
                        }
                    },
                    "organization_name": organization_name,
                    "count": 0
                }
            
            total_reviews = int(row.total_reviews)
            average_rating = float(row.average_rating or 0.0)
            
            rating_distribution = {
                "5": int(row.rating_5 or 0),
                "4": int(row.rating_4 or 0),
                "3": int(row.rating_3 or 0),
                "2": int(row.rating_2 or 0),
                "1": int(row.rating_1 or 0)
            }
            
            # 비율 계산
            rating_percentages = {
                "5": (rating_distribution["5"] / total_reviews * 100) if total_reviews > 0 else 0.0,
                "4": (rating_distribution["4"] / total_reviews * 100) if total_reviews > 0 else 0.0,
                "3": (rating_distribution["3"] / total_reviews * 100) if total_reviews > 0 else 0.0,
                "2": (rating_distribution["2"] / total_reviews * 100) if total_reviews > 0 else 0.0,
                "1": (rating_distribution["1"] / total_reviews * 100) if total_reviews > 0 else 0.0
            }
            
            return {
                "success": True,
                "data": {
                    "total_reviews": total_reviews,
                    "average_rating": round(average_rating, 2),
                    "rating_distribution": rating_distribution,
                    "rating_percentages": {
                        "5": round(rating_percentages["5"], 2),
                        "4": round(rating_percentages["4"], 2),
                        "3": round(rating_percentages["3"], 2),
                        "2": round(rating_percentages["2"], 2),
                        "1": round(rating_percentages["1"], 2)
                    }
                },
                "organization_name": organization_name,
                "count": total_reviews
            }
            
        finally:
            db.close()
            
    except Exception as e:
        return {
            "success": False,
            "data": {
                "total_reviews": 0,
                "average_rating": 0.0,
                "rating_distribution": {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0},
                "rating_percentages": {"5": 0.0, "4": 0.0, "3": 0.0, "2": 0.0, "1": 0.0}
            },
            "organization_name": organization_name,
            "error": str(e),
            "count": 0
        }

