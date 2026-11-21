import itertools
import math
import secrets
from typing import Iterable, List, Sequence, Tuple

import httpx
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.geo import haversine_km
from app.models import PlaceSearch, PointOfInterest, RoutePlan
from app.schemas import GeocodedPlace, POICandidate


POI_TAGS = {
    "tourism": ["attraction", "artwork", "museum", "viewpoint"],
    "historic": ["monument", "memorial", "building", "archaeological_site"],
    "leisure": ["park", "garden"],
    "amenity": ["cafe", "library", "theatre", "marketplace"],
}


def generate_share_token() -> str:
    """Return a URL-safe token suitable for public read-only route links."""
    return secrets.token_urlsafe(16)


def _unique_share_token(db: Session) -> str:
    token = generate_share_token()
    while db.query(RoutePlan).filter(RoutePlan.share_token == token).first() is not None:
        token = generate_share_token()
    return token


async def geocode_address(address: str) -> GeocodedPlace:
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": settings.user_agent}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{settings.nominatim_base_url}/search", params=params, headers=headers)
        response.raise_for_status()
        results = response.json()

    if not results:
        raise ValueError("No matching place found. Try a more specific address or landmark.")

    first = results[0]
    return GeocodedPlace(
        query=address,
        display_name=first.get("display_name", address),
        lat=float(first["lat"]),
        lon=float(first["lon"]),
    )


def _overpass_query(lat: float, lon: float, radius_m: int) -> str:
    clauses = []
    for key, values in POI_TAGS.items():
        for value in values:
            clauses.append(f'node(around:{radius_m},{lat},{lon})["{key}"="{value}"];')
            clauses.append(f'way(around:{radius_m},{lat},{lon})["{key}"="{value}"];')
            clauses.append(f'relation(around:{radius_m},{lat},{lon})["{key}"="{value}"];')
    return "[out:json][timeout:25];(" + "".join(clauses) + ");out center tags 60;"


def _category_from_tags(tags: dict) -> str:
    for key in ("tourism", "historic", "leisure", "amenity"):
        if key in tags:
            return str(tags[key]).replace("_", " ").title()
    return "Point of interest"


def _address_from_tags(tags: dict) -> str | None:
    parts = [
        tags.get("addr:housenumber"),
        tags.get("addr:street"),
        tags.get("addr:city"),
    ]
    text = " ".join(str(part) for part in parts if part)
    return text or None


async def fetch_nearby_pois(lat: float, lon: float) -> List[POICandidate]:
    query = _overpass_query(lat, lon, settings.search_radius_m)
    headers = {"User-Agent": settings.user_agent}
    candidates: list[POICandidate] = []

    try:
        async with httpx.AsyncClient(timeout=35) as client:
            response = await client.post(settings.overpass_url, data={"data": query}, headers=headers)
            response.raise_for_status()
            data = response.json()
    except Exception:
        return fallback_pois(lat, lon)

    seen_names: set[str] = set()
    for element in data.get("elements", []):
        tags = element.get("tags", {}) or {}
        name = tags.get("name")
        poi_lat = element.get("lat") or element.get("center", {}).get("lat")
        poi_lon = element.get("lon") or element.get("center", {}).get("lon")
        if not name or poi_lat is None or poi_lon is None:
            continue
        normalized = str(name).strip().lower()
        if normalized in seen_names:
            continue
        seen_names.add(normalized)
        distance = haversine_km(lat, lon, float(poi_lat), float(poi_lon))
        if distance <= 0.05:
            continue
        score = max(0.1, 2.0 - distance)
        candidates.append(
            POICandidate(
                name=str(name),
                category=_category_from_tags(tags),
                lat=float(poi_lat),
                lon=float(poi_lon),
                osm_id=f"{element.get('type', 'node')}/{element.get('id')}",
                address=_address_from_tags(tags),
                score=score,
            )
        )

    if len(candidates) < 3:
        return fallback_pois(lat, lon)

    return sorted(candidates, key=lambda poi: poi.score, reverse=True)[:10]


def fallback_pois(lat: float, lon: float) -> List[POICandidate]:
    offsets = [
        (0.0040, 0.0000, "Pocket Park", "Park"),
        (0.0000, 0.0045, "Neighborhood Cafe", "Cafe"),
        (-0.0035, -0.0025, "Local Landmark", "Landmark"),
        (0.0025, -0.0040, "Community Garden", "Garden"),
    ]
    return [
        POICandidate(name=name, category=category, lat=lat + dlat, lon=lon + dlon, score=1.0)
        for dlat, dlon, name, category in offsets
    ]


def _loop_distance(start: tuple[float, float], stops: Sequence[POICandidate]) -> float:
    points = [start] + [(poi.lat, poi.lon) for poi in stops] + [start]
    return sum(haversine_km(a[0], a[1], b[0], b[1]) for a, b in zip(points, points[1:]))


def choose_best_loop(start_lat: float, start_lon: float, candidates: Sequence[POICandidate]) -> Tuple[List[POICandidate], float]:
    top = list(candidates)[:8]
    best_route: list[POICandidate] | None = None
    best_distance = math.inf
    start = (start_lat, start_lon)

    for trio in itertools.combinations(top, 3):
        for order in itertools.permutations(trio):
            distance = _loop_distance(start, order)
            if distance < best_distance:
                best_distance = distance
                best_route = list(order)

    if best_route is None:
        best_route = list(top[:3])
        best_distance = _loop_distance(start, best_route)

    return best_route, best_distance


def save_route_plan(db: Session, place: GeocodedPlace, stops: Sequence[POICandidate], total_distance_km: float) -> RoutePlan:
    search = PlaceSearch(query=place.query, display_name=place.display_name, lat=place.lat, lon=place.lon)
    db.add(search)
    db.flush()

    plan = RoutePlan(
        search_id=search.id,
        title=f"Walking loop near {place.display_name.split(',')[0]}",
        start_lat=place.lat,
        start_lon=place.lon,
        total_distance_km=total_distance_km,
        share_token=_unique_share_token(db),
    )
    db.add(plan)
    db.flush()

    for index, stop in enumerate(stops, start=1):
        db.add(
            PointOfInterest(
                route_plan_id=plan.id,
                name=stop.name,
                category=stop.category,
                lat=stop.lat,
                lon=stop.lon,
                stop_order=index,
                osm_id=stop.osm_id,
                address=stop.address,
            )
        )

    db.commit()
    db.refresh(plan)
    return plan


def get_route_plan(db: Session, plan_id: int) -> RoutePlan | None:
    return (
        db.query(RoutePlan)
        .options(joinedload(RoutePlan.search), joinedload(RoutePlan.pois))
        .filter(RoutePlan.id == plan_id)
        .first()
    )


def get_route_plan_by_share_token(db: Session, share_token: str) -> RoutePlan | None:
    return (
        db.query(RoutePlan)
        .options(joinedload(RoutePlan.search), joinedload(RoutePlan.pois))
        .filter(RoutePlan.share_token == share_token)
        .first()
    )
