from pydantic import BaseModel

class FacilityOut(BaseModel):
    cutr_facl_id: int
    name: str | None = None
    type: str | None = None
    lat: float | None = None
    lon: float | None = None

    class Config:
        from_attributes = True

class RecommendationOut(BaseModel):
    facility_id: int
    name: str | None = None
    type: str | None = None
    score_culture: float | None = None
