from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

# 기존 postgres DB (보고서 저장용 - deprecated)
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# capstone DB (팀원 데이터 + 새 보고서 저장용)
# capstone_database_url이 없으면 database_url을 기본값으로 사용
_capstone_url = settings.capstone_database_url or settings.database_url
capstone_engine = create_engine(_capstone_url, pool_pre_ping=True)
CapstoneSessionLocal = sessionmaker(bind=capstone_engine, autocommit=False, autoflush=False)


def get_db():
    """기존 postgres DB 세션 (deprecated - 호환성 유지용)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_capstone_db():
    """capstone DB 세션 (팀원 데이터 + 새 보고서용)"""
    db = CapstoneSessionLocal()
    try:
        yield db
    finally:
        db.close()
