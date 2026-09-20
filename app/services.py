import json
from typing import Any

import httpx

from app.config import settings
from app.geo import Coord, bearing_offset, haversine_m


class LocationNotFound(Exception):
    pass


async def geocode_address(query: str) -> dict[str, Any]:
    params = {"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 0}
    headers = {"User-Agent": settings.user_agent}
    async with httpx.AsyncClient(timeout=12, headers=headers) as client:
        response = await client.get(f"{settings.nominatim_base_url}/search", params=params)
        response.raise_for_status()
        results = response.json()
    if not results:
        raise LocationNotFound(f"Could not find '{query}'")
    first = results[0]
    return {
        "query": query,
        "display_name": first.get("display_name", query),
        "lat": float(first["lat"]),
        "lng": float(first["lon"]),
    }


def category_from_tags(tags: dict[str, Any]) -> str:
    for key in ("tourism", "amenity", "leisure", "historic", "shop"):
        if key in tags:
            return str(tags[key]).replace("_", " ").title()
    return "Point of interest"


def name_from_tags(tags: dict[str, Any], fallback: str) -> str:
    name = tags.get("name") or tags.get("brand") or tags.get("operator")
    return str(name).strip() if name else fallback


async def fetch_nearby_pois(lat: float, lng: float, radius_m: int | None = None) -> list[dict[str, Any]]:
    radius = radius_m or settings.search_radius_m
    query = f"""
    [out:json][timeout:12];
    (
      node(around:{radius},{lat},{lng})[tourism][name];
      node(around:{radius},{lat},{lng})[historic][name];
      node(around:{radius},{lat},{lng})[leisure][name];
      node(around:{radius},{lat},{lng})[amenity~"cafe|restaurant|library|theatre|arts_centre|marketplace|place_of_worship"][name];
      node(around:{radius},{lat},{lng})[shop~"books|bakery|coffee|art|antiques"][name];
    );
    out center 40;
    """
    headers = {"User-Agent": settings.user_agent}
    try:
        async with httpx.AsyncClient(timeout=18, headers=headers) as client:
            response = await client.post(settings.overpass_url, data={"data": query})
            response.raise_for_status()
            elements = response.json().get("elements", [])
    except Exception:
        return fallback_pois(lat, lng)

    seen: set[tuple[str, int, int]] = set()
    pois: list[dict[str, Any]] = []
    start = Coord(lat, lng)
    for idx, el in enumerate(elements):
        tags = el.get("tags", {})
        poi_lat = el.get("lat") or el.get("center", {}).get("lat")
        poi_lng = el.get("lon") or el.get("center", {}).get("lon")
        if poi_lat is None or poi_lng is None:
            continue
        dist = haversine_m(start, Coord(float(poi_lat), float(poi_lng)))
        if dist < 80 or dist > radius * 1.2:
            continue
        name = name_from_tags(tags, f"Local stop {idx + 1}")
        key = (name.lower(), round(float(poi_lat), 4), round(float(poi_lng), 4))
        if key in seen:
            continue
        seen.add(key)
        pois.append({
            "name": name,
            "category": category_from_tags(tags),
            "lat": float(poi_lat),
            "lng": float(poi_lng),
            "distance_m": dist,
            "source": "osm",
            "raw_tags": json.dumps(tags),
        })

    pois.sort(key=lambda p: (abs(p["distance_m"] - 450), p["distance_m"]))
    if len(pois) < 3:
        return pois + fallback_pois(lat, lng, start_index=len(pois))[: 3 - len(pois)]
    return pois[:12]


def fallback_pois(lat: float, lng: float, start_index: int = 0) -> list[dict[str, Any]]:
    labels = [
        ("Neighborhood viewpoint", "Scenic spot", 320, 35),
        ("Pocket park pause", "Park", 420, 155),
        ("Local cafe corner", "Cafe", 360, 275),
        ("Quiet street mural", "Public art", 520, 90),
    ]
    stops = []
    start = Coord(lat, lng)
    for name, category, distance, bearing in labels[start_index:]:
        c = bearing_offset(lat, lng, distance, bearing)
        stops.append({
            "name": name,
            "category": category,
            "lat": c.lat,
            "lng": c.lng,
            "distance_m": haversine_m(start, c),
            "source": "fallback",
            "raw_tags": "{}",
        })
    return stops
