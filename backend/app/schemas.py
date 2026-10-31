from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, model_validator

class ValidationPolicy(BaseModel):
    maximum_speed_mpm: float = Field(default=3000, gt=0, lt=100000000, allow_inf_nan=False)
    clock_tolerance_seconds: int = Field(default=5, ge=0, le=300)

class RaceCreate(ValidationPolicy):
    club_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    release_latitude: float = Field(ge=-90, le=90)
    release_longitude: float = Field(ge=-180, le=180)
    scheduled_release_at: datetime | None = None
    minimum_speed_mpm: float = Field(default=500, ge=0, allow_inf_nan=False)
    display_speed_unit: Literal["m/min","m/s","km/h"] = "m/min"
    guest_ranking_mode: Literal["separate","combined"] = "separate"

    @model_validator(mode='after')
    def ordered_speed_limits(self):
        if self.maximum_speed_mpm <= self.minimum_speed_mpm:
            raise ValueError('Maximum speed must exceed minimum speed')
        return self

class EntryCreate(BaseModel):
    pigeon_id: UUID
    expected_method: Literal["RFID","QR"]

class RaceOut(BaseModel):
    id: UUID
    name: str
    status: str
    guest_ranking_mode: str
    model_config = {"from_attributes": True}

class EntryOut(BaseModel):
    id: UUID
    race_id: UUID
    pigeon_id: UUID
    distance_meters: float
    expected_method: str
    model_config = {"from_attributes": True}
