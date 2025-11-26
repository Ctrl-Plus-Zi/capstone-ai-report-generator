from contextlib import asynccontextmanager, contextmanager
from sqlalchemy.orm import Session
from app.db.session import SessionLocal


@asynccontextmanager
async def get_db_context_async():
    """데이터베이스 컨텍스트 매니저 (비동기 지원)"""
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
    """데이터베이스 컨텍스트 매니저 (동기)"""
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_sync():
    """동기식 데이터베이스 세션 (수동 close 필요)"""
    return SessionLocal()