from datetime import datetime
from pydantic import BaseModel


class StopOut(BaseModel):
    name: str
    category: str
    lat: float
    lng: float
    distance_m: float
    stop_order: int


class RoutePlanOut(BaseModel):
    id: int
    start_query: str
    start_lat: float
    start_lng: float
    total_distance_m: float
    generated_at: datetime
    stops: list[StopOut]

    model_config = {"from_attributes": True}
