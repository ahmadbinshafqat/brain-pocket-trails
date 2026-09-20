from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlaceSearch(Base):
    __tablename__ = "place_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    query: Mapped[str] = mapped_column(String(300), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    plans: Mapped[list["RoutePlan"]] = relationship(back_populates="search")


class RoutePlan(Base):
    __tablename__ = "route_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("place_searches.id"), nullable=False)
    start_query: Mapped[str] = mapped_column(String(300), nullable=False)
    start_lat: Mapped[float] = mapped_column(Float, nullable=False)
    start_lng: Mapped[float] = mapped_column(Float, nullable=False)
    total_distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    search: Mapped[PlaceSearch] = relationship(back_populates="plans")
    stops: Mapped[list["PointOfInterest"]] = relationship(back_populates="route_plan", cascade="all, delete-orphan", order_by="PointOfInterest.stop_order")


class PointOfInterest(Base):
    __tablename__ = "points_of_interest"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route_plan_id: Mapped[int] = mapped_column(ForeignKey("route_plans.id"), nullable=False)
    stop_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="osm", nullable=False)
    raw_tags: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    route_plan: Mapped[RoutePlan] = relationship(back_populates="stops")
