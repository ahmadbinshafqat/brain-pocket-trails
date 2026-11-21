from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class PlaceSearch(Base):
    __tablename__ = "place_searches"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String(500), nullable=False, index=True)
    display_name = Column(String(1000), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    route_plans = relationship("RoutePlan", back_populates="search", cascade="all, delete-orphan")


class RoutePlan(Base):
    __tablename__ = "route_plans"

    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("place_searches.id"), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    start_lat = Column(Float, nullable=False)
    start_lon = Column(Float, nullable=False)
    total_distance_km = Column(Float, nullable=False)
    share_token = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    search = relationship("PlaceSearch", back_populates="route_plans")
    pois = relationship(
        "PointOfInterest",
        back_populates="route_plan",
        cascade="all, delete-orphan",
        order_by="PointOfInterest.stop_order",
    )


class PointOfInterest(Base):
    __tablename__ = "points_of_interest"

    id = Column(Integer, primary_key=True, index=True)
    route_plan_id = Column(Integer, ForeignKey("route_plans.id"), nullable=False, index=True)
    name = Column(String(300), nullable=False)
    category = Column(String(100), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    stop_order = Column(Integer, nullable=False)
    osm_id = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)

    route_plan = relationship("RoutePlan", back_populates="pois")
