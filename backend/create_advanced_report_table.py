from app.config import settings
from app.db.base import Base
from app.models.advanced_report import AdvancedReport
from sqlalchemy import create_engine

print(f"Database connection: {settings.database_url}")

engine = create_engine(settings.database_url, pool_pre_ping=True)

print("Creating advanced_reports table...")
Base.metadata.create_all(bind=engine)

print("Table creation complete!")

from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"Existing tables: {tables}")

