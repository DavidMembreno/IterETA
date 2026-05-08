from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


#  Auth

class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=4)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthOut(BaseModel):
    token: str
    username: str


#  Vehicles

class VehicleCreate(BaseModel):
    nickname: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    current_mileage: Optional[int] = None


class VehicleOut(VehicleCreate):
    id: int

    class Config:
        from_attributes = True


class VehicleMileageUpdate(BaseModel):
    current_mileage: int


#  Trips

class TripStart(BaseModel):
    vehicle_id: int
    start_label: str


class TripEnd(BaseModel):
    end_label: str


class TripOut(BaseModel):
    id: int
    vehicle_id: int
    start_label: str
    end_label: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: Optional[float] = None

    class Config:
        from_attributes = True


#  Safety Incidents

class SafetyIncidentCreate(BaseModel):
    trip_id: int
    severity: int = Field(ge=1, le=10)
    description: Optional[str] = None


class SafetyIncidentOut(BaseModel):
    id: int
    trip_id: int
    severity: int
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


#  Maintenance

class MaintenanceCreate(BaseModel):
    vehicle_id: int
    service_type: str
    cost: Optional[float] = None
    mileage: Optional[int] = None
    notes: Optional[str] = None


class MaintenanceOut(BaseModel):
    id: int
    vehicle_id: int
    service_type: str
    cost: Optional[float] = None
    mileage: Optional[int] = None
    service_date: datetime
    notes: Optional[str] = None

    class Config:
        from_attributes = True


#  User Settings

class SettingOut(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class SettingUpdate(BaseModel):
    value: str


class CustomIntervalCreate(BaseModel):
    service_type: str
    interval_miles: int = Field(gt=0)