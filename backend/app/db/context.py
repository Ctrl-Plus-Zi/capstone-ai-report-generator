from contextlib import asynccontextmanager, contextmanager
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, CapstoneSessionLocal


# ============================================================================
# 기존 postgres DB 컨텍스트 (deprecated - 호환성 유지용)
# ============================================================================

@asynccontextmanager
async def get_db_context_async():
    """데이터베이스 컨텍스트 매니저 (비동기 지원) - deprecated"""
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context():
    """데이터베이스 컨텍스트 매니저 (동기) - deprecated"""
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_sync():
    """동기식 데이터베이스 세션 (수동 close 필요) - deprecated"""
    return SessionLocal()


# ============================================================================
# capstone DB 컨텍스트 (팀원 데이터 + 새 보고서용)
# ============================================================================

@asynccontextmanager
async def get_capstone_db_context_async():
    """capstone DB 컨텍스트 매니저 (비동기 지원)"""
    db: Session = CapstoneSessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_capstone_db_context():
    """capstone DB 컨텍스트 매니저 (동기) - 데이터 조회용"""
    db: Session = CapstoneSessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_capstone_db_sync():
    """capstone DB 동기식 세션 (수동 close 필요)"""
    return CapstoneSessionLocal()