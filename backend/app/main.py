"""Prototype calculation endpoints; not an official clocking service."""
from datetime import datetime
from typing import Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .calculations import distance_meters, speed_mpm, convert_speed

app = FastAPI(title="Dove Racing Prototype API", version="0.2.0")

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
