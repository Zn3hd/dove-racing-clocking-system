"""Prototype calculation endpoints; not an official clocking service."""
from datetime import datetime
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from .calculations import distance_meters, speed_mpm, convert_speed

from .routers.clubs import router as clubs_router
from .routers.races import router as races_router
from .routers.entries import router as entries_router
from .routers.auth import router as auth_router
from .routers.first_admin import router as first_admin_router
from .routers.participants import router as participants_router
from .routers.clocking import router as clocking_router
from .routers.results_preview import router as results_preview_router
from .routers.finalization import router as finalization_router
from .routers.guest_verification import router as guest_verification_router
from .routers.device_gateway import router as device_gateway_router
from .routers.clocking_sources import router as clocking_sources_router
from .routers.manual_clocking import router as manual_clocking_router
from .routers.sms_clocking import router as sms_clocking_router
from .routers.messenger_clocking import router as messenger_clocking_router

app = FastAPI(title="Pigeon Racing Clocking System API", version="0.2.0")

# Same-origin dashboard: no cross-origin token transmission or frontend build.
app.mount("/dashboard", StaticFiles(directory=Path(__file__).resolve().parents[1] / "dashboard", html=True), name="dashboard")


@app.middleware("http")
async def dashboard_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/dashboard"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(self)"
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", include_in_schema=False)
def dashboard_home():
    return RedirectResponse("/dashboard/")

class FlightCalculation(BaseModel):
    release_latitude: float = Field(ge=-90, le=90)
    release_longitude: float = Field(ge=-180, le=180)
    loft_latitude: float = Field(ge=-90, le=90)
    loft_longitude: float = Field(ge=-180, le=180)
    release_at: datetime
    arrival_at: datetime
    minimum_speed_mpm: float = Field(default=500, ge=0)
    display_unit: Literal["m/min", "m/s", "km/h"] = "m/min"

@app.get("/health")
def health():
    return {"status": "ok", "mode": "development", "official_clocking_enabled": False}

@app.post("/calculations/flight")
def calculate_flight(payload: FlightCalculation):
    try:
        distance = distance_meters(payload.release_latitude, payload.release_longitude,
                                   payload.loft_latitude, payload.loft_longitude)
        velocity = speed_mpm(distance, payload.release_at, payload.arrival_at)
        return {
            "distance_meters": round(distance, 3),
            "flight_duration_seconds": (payload.arrival_at - payload.release_at).total_seconds(),
            "speed_mpm": round(velocity, 4),
            "display_speed": round(convert_speed(velocity, payload.display_unit), 4),
            "display_unit": payload.display_unit,
            "qualifies_minimum_speed": velocity >= payload.minimum_speed_mpm,
            "note": "Simulation only; not a verified race result"
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


app.include_router(clubs_router)
app.include_router(races_router)
app.include_router(entries_router)
app.include_router(auth_router)
app.include_router(first_admin_router)
app.include_router(participants_router)
app.include_router(clocking_router)
app.include_router(results_preview_router)
app.include_router(finalization_router)
app.include_router(guest_verification_router)
app.include_router(device_gateway_router)
app.include_router(clocking_sources_router)
app.include_router(manual_clocking_router)
app.include_router(sms_clocking_router)
app.include_router(messenger_clocking_router)
