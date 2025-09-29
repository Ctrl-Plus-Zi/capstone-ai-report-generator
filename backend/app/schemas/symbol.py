from datetime import datetime

from pydantic import BaseModel


class SymbolCreate(BaseModel):
    code: str
    name: str


class SymbolRead(BaseModel):
    id: int
    code: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True
