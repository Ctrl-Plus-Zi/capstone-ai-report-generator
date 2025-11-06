from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    name: str

class UserRead(BaseModel):
    id: int
    email: EmailStr
    name: str

    class Config:
        from_attributes = True  # Pydantic v2: SQLAlchemy 객체 -> 스키마 변환
