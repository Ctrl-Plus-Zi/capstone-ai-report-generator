from app.config import settings
from sqlalchemy import create_engine, text

print(f"Database connection: {settings.database_url}")

engine = create_engine(settings.database_url, pool_pre_ping=True)

print("Dropping advanced_reports table...")
with engine.connect() as conn:
    conn.execute(text("DROP TABLE IF EXISTS advanced_reports CASCADE"))
    conn.commit()

print("Table dropped successfully!")

