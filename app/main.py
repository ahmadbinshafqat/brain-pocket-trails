from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, init_db
from app.geo import optimize_three_stop_loop
from app.models import PlaceSearch, PointOfInterest, RoutePlan
from app.schemas import RoutePlanOut
from app.services import LocationNotFound, fetch_nearby_pois, geocode_address

app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "app_name": settings.app_name})


@app.post("/plan")
async def create_plan(query: str = Form(...), db: Session = Depends(get_db)):
    clean_query = query.strip()
    if len(clean_query) < 3:
        return RedirectResponse("/?error=Please enter a more specific starting location.", status_code=303)

    try:
        place = await geocode_address(clean_query)
    except LocationNotFound:
        return RedirectResponse("/?error=That location was not found. Try a landmark or full address.", status_code=303)
    except Exception:
        return RedirectResponse("/?error=Geocoding service is unavailable. Please try again shortly.", status_code=303)

    pois = await fetch_nearby_pois(place["lat"], place["lng"])
    ordered_stops, total_distance = optimize_three_stop_loop(place["lat"], place["lng"], pois)

    search = PlaceSearch(query=clean_query, lat=place["lat"], lng=place["lng"])
    db.add(search)
    db.flush()

    plan = RoutePlan(
        search_id=search.id,
        start_query=place.get("display_name") or clean_query,
        start_lat=place["lat"],
        start_lng=place["lng"],
        total_distance_m=total_distance,
    )
    db.add(plan)
    db.flush()

    for idx, stop in enumerate(ordered_stops, start=1):
        db.add(PointOfInterest(
            route_plan_id=plan.id,
            stop_order=idx,
            name=stop["name"][:250],
            category=stop["category"][:100],
            lat=stop["lat"],
            lng=stop["lng"],
            distance_m=stop["distance_m"],
            source=stop.get("source", "osm"),
            raw_tags=stop.get("raw_tags", "{}"),
        ))
    db.commit()
    return RedirectResponse(f"/plans/{plan.id}", status_code=303)


@app.get("/plans/{plan_id}", response_class=HTMLResponse)
def show_plan(plan_id: int, request: Request, db: Session = Depends(get_db)):
    plan = db.get(RoutePlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Route plan not found")
    coordinates = [[plan.start_lat, plan.start_lng]] + [[s.lat, s.lng] for s in plan.stops] + [[plan.start_lat, plan.start_lng]]
    return templates.TemplateResponse("plan.html", {
        "request": request,
        "plan": plan,
        "coordinates": coordinates,
        "km": plan.total_distance_m / 1000,
        "app_name": settings.app_name,
    })


@app.get("/api/plans/{plan_id}", response_model=RoutePlanOut)
def api_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.get(RoutePlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Route plan not found")
    return plan


@app.get("/health")
def health():
    return {"status": "ok"}
