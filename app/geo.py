import itertools
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Coord:
    lat: float
    lng: float


def haversine_m(a: Coord, b: Coord) -> float:
    radius_m = 6_371_000
    lat1 = math.radians(a.lat)
    lat2 = math.radians(b.lat)
    dlat = math.radians(b.lat - a.lat)
    dlng = math.radians(b.lng - a.lng)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * radius_m * math.asin(math.sqrt(h))


def loop_distance_m(start: Coord, stops: list[dict]) -> float:
    if not stops:
        return 0.0
    coords = [start] + [Coord(s["lat"], s["lng"]) for s in stops] + [start]
    return sum(haversine_m(coords[i], coords[i + 1]) for i in range(len(coords) - 1))


def optimize_three_stop_loop(start_lat: float, start_lng: float, pois: list[dict]) -> tuple[list[dict], float]:
    if len(pois) < 3:
        raise ValueError("At least 3 POIs are required")

    start = Coord(start_lat, start_lng)
    best_route: tuple[dict, ...] | None = None
    best_distance = float("inf")

    candidates = pois[:8]
    for trio in itertools.combinations(candidates, 3):
        for route in itertools.permutations(trio):
            dist = loop_distance_m(start, list(route))
            if dist < best_distance:
                best_distance = dist
                best_route = route

    assert best_route is not None
    return [dict(stop) for stop in best_route], best_distance


def bearing_offset(lat: float, lng: float, distance_m: float, bearing_deg: float) -> Coord:
    radius_m = 6_371_000
    bearing = math.radians(bearing_deg)
    lat1 = math.radians(lat)
    lng1 = math.radians(lng)
    angular = distance_m / radius_m

    lat2 = math.asin(math.sin(lat1) * math.cos(angular) + math.cos(lat1) * math.sin(angular) * math.cos(bearing))
    lng2 = lng1 + math.atan2(
        math.sin(bearing) * math.sin(angular) * math.cos(lat1),
        math.cos(angular) - math.sin(lat1) * math.sin(lat2),
    )
    return Coord(math.degrees(lat2), math.degrees(lng2))
