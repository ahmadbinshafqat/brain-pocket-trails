from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AddressRequest(BaseModel):
    address: str = Field(..., min_length=3, max_length=500)


class GeocodedPlace(BaseModel):
    query: str
    display_name: str
    lat: float
    lon: float


class POICandidate(BaseModel):
    name: str
    category: str
    lat: float
    lon: float
    osm_id: Optional[str] = None
    address: Optional[str] = None
    score: float = 0.0


class PointOfInterestRead(BaseModel):
    id: int
    name: str
    category: str
    lat: float
    lon: float
    stop_order: int
    osm_id: Optional[str] = None
    address: Optional[str] = None

    class Config:
        from_attributes = True


class RoutePlanRead(BaseModel):
    id: int
    title: str
    start_lat: float
    start_lon: float
    total_distance_km: float
    share_token: str
    created_at: datetime
    pois: List[PointOfInterestRead]

    class Config:
        from_attributes = True
