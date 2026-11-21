from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, engine, get_db
from app.models import RoutePlan
from app.services import (
    choose_best_loop,
    fetch_nearby_pois,
    generate_share_token,
    geocode_address,
    get_route_plan,
    get_route_plan_by_share_token,
    save_route_plan,
)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_share_tokens()


def ensure_share_tokens() -> None:
    """Keep existing SQLite databases compatible with the sharing feature.

    SQLAlchemy's create_all does not add columns to existing tables. This small
    compatibility step creates/backfills RoutePlan.share_token for local MVP
    databases so users do not need a migration tool to try the feature.
    """
    inspector = inspect(engine)
    if "route_plans" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("route_plans")}
    with engine.begin() as connection:
        if "share_token" not in columns:
            connection.execute(text("ALTER TABLE route_plans ADD COLUMN share_token VARCHAR(64)"))

    with Session(engine) as db:
        plans = db.query(RoutePlan).filter((RoutePlan.share_token.is_(None)) | (RoutePlan.share_token == "")).all()
        used = {token for (token,) in db.query(RoutePlan.share_token).filter(RoutePlan.share_token.isnot(None)).all() if token}
        for plan in plans:
            token = generate_share_token()
            while token in used:
                token = generate_share_token()
            used.add(token)
            plan.share_token = token
        if plans:
            db.commit()

    inspector = inspect(engine)
    indexes = {index["name"] for index in inspector.get_indexes("route_plans")}
    with engine.begin() as connection:
        if "ix_route_plans_share_token" not in indexes:
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_route_plans_share_token ON route_plans (share_token)"))


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request, "app_name": settings.app_name})


@app.post("/plan", response_class=HTMLResponse)
async def create_plan(request: Request, address: str = Form(...), db: Session = Depends(get_db)) -> HTMLResponse:
    try:
        place = await geocode_address(address)
        candidates = await fetch_nearby_pois(place.lat, place.lon)
        stops, distance = choose_best_loop(place.lat, place.lon, candidates)
        plan = save_route_plan(db, place, stops, distance)
    except ValueError as exc:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "app_name": settings.app_name, "error": str(exc), "address": address},
            status_code=400,
        )
    except Exception:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "app_name": settings.app_name,
                "error": "Something went wrong while building your route. Please try again.",
                "address": address,
            },
            status_code=500,
        )

    return RedirectResponse(url=f"/plan/{plan.id}", status_code=303)


@app.get("/plan/{plan_id}", response_class=HTMLResponse)
def show_plan(plan_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    plan = get_route_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Route plan not found")
    share_url = str(request.url_for("show_shared_plan", share_token=plan.share_token))
    return templates.TemplateResponse(
        "plan.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "plan": plan,
            "share_url": share_url,
            "is_shared_view": False,
        },
    )


@app.get("/share/{share_token}", response_class=HTMLResponse, name="show_shared_plan")
def show_shared_plan(share_token: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    plan = get_route_plan_by_share_token(db, share_token)
    if plan is None:
        raise HTTPException(status_code=404, detail="Shared route not found")
    share_url = str(request.url_for("show_shared_plan", share_token=plan.share_token))
    return templates.TemplateResponse(
        "plan.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "plan": plan,
            "share_url": share_url,
            "is_shared_view": True,
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
