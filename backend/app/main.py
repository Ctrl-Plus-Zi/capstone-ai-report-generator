import asyncio
import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.report import Report
from app.schemas.report import GenerateReportRequest, GenerateReportResponse

from .api import simple_report, agent_report, block_report


logger = logging.getLogger("uvicorn.error")

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:4173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(simple_report.router)
app.include_router(agent_report.router)
app.include_router(block_report.router)  # Server-Driven UI 블록 기반 보고서

@app.on_event("startup")
async def start_heartbeat():
    # 하트비트 태스크 시작
    app.state.heartbeat_task = asyncio.create_task(heartbeat())
    logger.info("하트비트 태스크 시작")


@app.on_event("shutdown")
async def stop_heartbeat():
    logger.info("하트비트 태스크 종료")
    
    # 하트비트 태스크 종료
    task = getattr(app.state, "heartbeat_task", None)
    if task:
        task.cancel()
    
    # WebSocket 연결 종료
    try:
        logger.info("모든 WebSocket 연결 종료")
    except Exception as e:
        logger.error(f"WebSocket 연결 종료 오류: {e}")


def log_db_ready(db: Session) -> None:
    db.execute(text("SELECT 1"))


async def heartbeat():
    while True:
        logger.info("Heartbeat: server is running")
        await asyncio.sleep(60)


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    logger.info("Health check endpoint called")
    return {"status": "ok"}


@app.get("/db-test", tags=["system"])
def db_test(db: Session = Depends(get_db)) -> dict[str, str]:
    log_db_ready(db)
    return {"db": "ok"}
