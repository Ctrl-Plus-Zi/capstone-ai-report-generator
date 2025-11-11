
from app.config import settings
from app.db.base import Base
from app.models.report import Report
from sqlalchemy import create_engine

print(f"데이터베이스 연결 중: {settings.database_url}")

engine = create_engine(settings.database_url, pool_pre_ping=True)

print("테이블 생성 중...")
Base.metadata.create_all(bind=engine)

print("테이블 생성 완료!")

# 생성된 테이블 확인
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"생성된 테이블: {tables}")
