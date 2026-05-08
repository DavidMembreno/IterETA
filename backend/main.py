from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import statistics
import csv
import io
import uuid
import bcrypt

from .database import Base, engine, get_db
from . import models, schemas

Base.metadata.create_all(bind=engine)

app = FastAPI(title="IterETA API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

#Default settings

DEFAULT_SETTINGS = [
    {"key": "oil_change_interval_miles", "value": "5000", "description": "Miles between oil changes"},
    {"key": "tire_rotation_interval_miles", "value": "7500", "description": "Miles between tire rotations"},
    {"key": "brake_service_interval_miles", "value": "20000", "description": "Miles between brake inspections"},
    {"key": "maintenance_time_gap_days", "value": "90", "description": "Days without any maintenance before a reminder fires"},
]

CUSTOM_INTERVAL_PREFIX = "custom_interval_"


def seed_default_settings(db: Session):
    for s in DEFAULT_SETTINGS:
        exists = db.query(models.UserSetting).filter(models.UserSetting.key == s["key"]).first()
        if not exists:
            db.add(models.UserSetting(**s))
    db.commit()


@app.on_event("startup")
def on_startup():
    db = next(get_db())
    try:
        seed_default_settings(db)
    finally:
        db.close()


def get_setting(db: Session, key: str, default: str = "0") -> str:
    row = db.query(models.UserSetting).filter(models.UserSetting.key == key).first()
    return row.value if row else default


# Auth helpers

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def get_current_user(
    x_token: str = Header(..., alias="X-Token"),
    db: Session = Depends(get_db),
) -> models.User:
    session = db.query(models.Session).filter(models.Session.token == x_token).first()
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please log in again.")
    return session.user


#Root

@app.get("/")
def root():
    return {"status": "IterETA backend running"}


#AUTH

@app.post("/auth/register", response_model=schemas.AuthOut)
def register(payload: schemas.RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken.")
    user = models.User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = str(uuid.uuid4())
    session = models.Session(user_id=user.id, token=token)
    db.add(session)
    db.commit()

    return {"token": token, "username": user.username}


@app.post("/auth/login", response_model=schemas.AuthOut)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")

    token = str(uuid.uuid4())
    session = models.Session(user_id=user.id, token=token)
    db.add(session)
    db.commit()

    return {"token": token, "username": user.username}


@app.post("/auth/logout")
def logout(
    x_token: str = Header(..., alias="X-Token"),
    db: Session = Depends(get_db),
):
    session = db.query(models.Session).filter(models.Session.token == x_token).first()
    if session:
        db.delete(session)
        db.commit()
    return {"logged_out": True}


@app.get("/auth/me")
def me(current_user: models.User = Depends(get_current_user)):
    return {"username": current_user.username}


#VEHICLES

@app.post("/vehicles", response_model=schemas.VehicleOut)
def create_vehicle(
    payload: schemas.VehicleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    v = models.Vehicle(**payload.model_dump(), user_id=current_user.id)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@app.get("/vehicles", response_model=list[schemas.VehicleOut])
def list_vehicles(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.query(models.Vehicle).filter(
        models.Vehicle.user_id == current_user.id
    ).order_by(models.Vehicle.id.desc()).all()


@app.get("/vehicles/{vehicle_id}", response_model=schemas.VehicleOut)
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    v = db.query(models.Vehicle).filter(
        models.Vehicle.id == vehicle_id,
        models.Vehicle.user_id == current_user.id,
    ).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return v


@app.patch("/vehicles/{vehicle_id}/mileage", response_model=schemas.VehicleOut)
def update_mileage(
    vehicle_id: int,
    payload: schemas.VehicleMileageUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    v = db.query(models.Vehicle).filter(
        models.Vehicle.id == vehicle_id,
        models.Vehicle.user_id == current_user.id,
    ).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    v.current_mileage = payload.current_mileage
    db.commit()
    db.refresh(v)
    return v


@app.delete("/vehicles/{vehicle_id}")
def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    v = db.query(models.Vehicle).filter(
        models.Vehicle.id == vehicle_id,
        models.Vehicle.user_id == current_user.id,
    ).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    db.delete(v)
    db.commit()
    return {"deleted": vehicle_id}


#TRIPS

@app.post("/trips/start", response_model=schemas.TripOut)
def start_trip(
    payload: schemas.TripStart,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.id == payload.vehicle_id,
        models.Vehicle.user_id == current_user.id,
    ).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    t = models.Trip(vehicle_id=payload.vehicle_id, start_label=payload.start_label)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@app.post("/trips/{trip_id}/end", response_model=schemas.TripOut)
def end_trip(
    trip_id: int,
    payload: schemas.TripEnd,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    t = db.query(models.Trip).join(models.Vehicle).filter(
        models.Trip.id == trip_id,
        models.Vehicle.user_id == current_user.id,
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Trip not found")
    if t.end_time is not None:
        raise HTTPException(status_code=400, detail="Trip already ended")
    t.end_label = payload.end_label
    t.end_time = datetime.utcnow()
    t.duration_minutes = round((t.end_time - t.start_time).total_seconds() / 60.0, 2)
    db.commit()
    db.refresh(t)
    return t


@app.get("/trips", response_model=list[schemas.TripOut])
def list_trips(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.query(models.Trip).join(models.Vehicle).filter(
        models.Vehicle.user_id == current_user.id
    ).order_by(models.Trip.id.desc()).all()


#SAFETY INCIDENTS

@app.post("/safety", response_model=schemas.SafetyIncidentOut)
def create_safety(
    payload: schemas.SafetyIncidentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    trip = db.query(models.Trip).join(models.Vehicle).filter(
        models.Trip.id == payload.trip_id,
        models.Vehicle.user_id == current_user.id,
    ).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    incident = models.SafetyIncident(**payload.model_dump())
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


@app.get("/safety", response_model=list[schemas.SafetyIncidentOut])
def list_safety(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.query(models.SafetyIncident).join(models.Trip).join(models.Vehicle).filter(
        models.Vehicle.user_id == current_user.id
    ).order_by(models.SafetyIncident.id.desc()).all()


#MAINTENANCE

@app.post("/maintenance", response_model=schemas.MaintenanceOut)
def create_maintenance(
    payload: schemas.MaintenanceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.id == payload.vehicle_id,
        models.Vehicle.user_id == current_user.id,
    ).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    record = models.MaintenanceRecord(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.get("/maintenance", response_model=list[schemas.MaintenanceOut])
def list_maintenance(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.query(models.MaintenanceRecord).join(models.Vehicle).filter(
        models.Vehicle.user_id == current_user.id
    ).order_by(models.MaintenanceRecord.id.desc()).all()


#SETTINGS

@app.get("/settings", response_model=list[schemas.SettingOut])
def get_settings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.query(models.UserSetting).order_by(models.UserSetting.key).all()


@app.put("/settings/{key}", response_model=schemas.SettingOut)
def update_setting(
    key: str,
    payload: schemas.SettingUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    row = db.query(models.UserSetting).filter(models.UserSetting.key == key).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    row.value = payload.value
    db.commit()
    db.refresh(row)
    return row


@app.post("/settings/custom-interval", response_model=schemas.SettingOut)
def add_custom_interval(
    payload: schemas.CustomIntervalCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    safe_key = payload.service_type.lower().strip().replace(" ", "_").replace("/", "_")
    key = f"{CUSTOM_INTERVAL_PREFIX}{safe_key}_miles"
    existing = db.query(models.UserSetting).filter(models.UserSetting.key == key).first()
    if existing:
        existing.value = str(payload.interval_miles)
        db.commit()
        db.refresh(existing)
        return existing
    row = models.UserSetting(
        key=key,
        value=str(payload.interval_miles),
        description=f"Miles between {payload.service_type} services (custom)",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.delete("/settings/custom-interval/{key}")
def delete_custom_interval(
    key: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not key.startswith(CUSTOM_INTERVAL_PREFIX):
        raise HTTPException(status_code=400, detail="Can only delete custom interval settings")
    row = db.query(models.UserSetting).filter(models.UserSetting.key == key).first()
    if not row:
        raise HTTPException(status_code=404, detail="Setting not found")
    db.delete(row)
    db.commit()
    return {"deleted": key}


#ETA & ANALYTICS

@app.get("/eta")
def get_eta(
    start_label: str = Query(...),
    end_label: str = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    past_trips = db.query(models.Trip).join(models.Vehicle).filter(
        models.Vehicle.user_id == current_user.id,
        models.Trip.start_label == start_label,
        models.Trip.end_label == end_label,
        models.Trip.duration_minutes.isnot(None),
    ).all()

    if not past_trips:
        raise HTTPException(status_code=404, detail=f"No completed trips found for route '{start_label}' to '{end_label}'")

    durations = [t.duration_minutes for t in past_trips]
    avg = round(statistics.mean(durations), 2)
    if len(durations) >= 2:
        conservative = round(avg + statistics.stdev(durations), 2)
        confidence = "high" if len(durations) >= 5 else "moderate"
    else:
        conservative = round(avg * 1.20, 2)
        confidence = "low"

    return {
        "route": f"{start_label} to {end_label}",
        "trip_count": len(durations),
        "avg_duration_minutes": avg,
        "conservative_eta_minutes": conservative,
        "confidence": confidence,
        "note": "Conservative ETA adds buffer for parking, delays, or variability.",
    }


@app.get("/analytics/routes")
def list_routes(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    trips = db.query(models.Trip).join(models.Vehicle).filter(
        models.Vehicle.user_id == current_user.id,
        models.Trip.duration_minutes.isnot(None),
    ).all()
    route_map = {}
    for t in trips:
        key = (t.start_label, t.end_label)
        route_map.setdefault(key, []).append(t.duration_minutes)
    return sorted([
        {"start_label": s, "end_label": e, "trip_count": len(d), "avg_duration_minutes": round(statistics.mean(d), 2)}
        for (s, e), d in route_map.items()
    ], key=lambda x: x["trip_count"], reverse=True)


@app.get("/analytics/reliability")
def reliability_summary(
    vehicle_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Trip).join(models.Vehicle).filter(models.Vehicle.user_id == current_user.id)
    if vehicle_id:
        query = query.filter(models.Trip.vehicle_id == vehicle_id)
    all_trips = query.all()
    completed = [t for t in all_trips if t.duration_minutes is not None]
    completion_rate = round(len(completed) / len(all_trips) * 100, 1) if all_trips else 0
    avg_duration = round(statistics.mean([t.duration_minutes for t in completed]), 2) if completed else None
    cutoff = datetime.utcnow() - timedelta(days=30)
    recent_incidents = db.query(models.SafetyIncident).join(models.Trip).join(models.Vehicle).filter(
        models.Vehicle.user_id == current_user.id,
        models.SafetyIncident.created_at >= cutoff,
    ).all()
    avg_severity = round(statistics.mean([i.severity for i in recent_incidents]), 2) if recent_incidents else None
    return {
        "total_trips": len(all_trips),
        "completed_trips": len(completed),
        "completion_rate_pct": completion_rate,
        "avg_duration_minutes": avg_duration,
        "recent_incidents_30d": len(recent_incidents),
        "avg_severity_30d": avg_severity,
    }


#SAFETY ALERTS

@app.get("/alerts")
def get_safety_alerts(
    vehicle_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    alerts = []
    now = datetime.utcnow()

    oil_interval = int(get_setting(db, "oil_change_interval_miles", "5000"))
    tire_interval = int(get_setting(db, "tire_rotation_interval_miles", "7500"))
    brake_interval = int(get_setting(db, "brake_service_interval_miles", "20000"))
    time_gap_days = int(get_setting(db, "maintenance_time_gap_days", "90"))

    custom_intervals = {}
    for row in db.query(models.UserSetting).filter(models.UserSetting.key.like(f"{CUSTOM_INTERVAL_PREFIX}%")).all():
        inner = row.key[len(CUSTOM_INTERVAL_PREFIX):]
        if inner.endswith("_miles"):
            custom_intervals[inner[:-6].replace("_", " ")] = int(row.value)

    incident_query = db.query(models.SafetyIncident).join(models.Trip).join(models.Vehicle).filter(
        models.Vehicle.user_id == current_user.id
    )
    if vehicle_id:
        incident_query = incident_query.filter(models.Trip.vehicle_id == vehicle_id)

    last_14d = now - timedelta(days=14)
    last_7d = now - timedelta(days=7)
    recent_14d = incident_query.filter(models.SafetyIncident.created_at >= last_14d).all()
    recent_7d = [i for i in recent_14d if i.created_at >= last_7d]
    last_10 = incident_query.order_by(models.SafetyIncident.id.desc()).limit(10).all()

    high_sev = [i for i in recent_14d if i.severity >= 7]
    if high_sev:
        alerts.append({"level": "HIGH", "rule": "high_severity_recent", "message": f"{len(high_sev)} incident(s) with severity 7+ in the last 14 days."})
    if last_10:
        avg_sev = statistics.mean([i.severity for i in last_10])
        if avg_sev >= 5:
            alerts.append({"level": "MODERATE", "rule": "elevated_avg_severity", "message": f"Average severity across last {len(last_10)} incidents is {round(avg_sev, 1)}."})
    if len(recent_7d) >= 3:
        alerts.append({"level": "MODERATE", "rule": "frequency_spike", "message": f"{len(recent_7d)} incidents in the last 7 days."})

    service_intervals = {
        "oil": ("oil & filter change", oil_interval),
        "tire rotation": ("tire rotation", tire_interval),
        "brake": ("brake", brake_interval),
        **{kw: (kw, mi) for kw, mi in custom_intervals.items()},
    }

    vehicles_query = db.query(models.Vehicle).filter(models.Vehicle.user_id == current_user.id)
    if vehicle_id:
        vehicles_query = vehicles_query.filter(models.Vehicle.id == vehicle_id)
    vehicles_to_check = vehicles_query.all()

    for vehicle in vehicles_to_check:
        if vehicle.current_mileage is None:
            continue
        for rule_key, (service_keyword, interval) in service_intervals.items():
            last_service = db.query(models.MaintenanceRecord).filter(
                models.MaintenanceRecord.vehicle_id == vehicle.id,
                models.MaintenanceRecord.service_type.ilike(f"%{service_keyword}%"),
                models.MaintenanceRecord.mileage.isnot(None),
            ).order_by(models.MaintenanceRecord.mileage.desc()).first()

            if last_service:
                miles_since = vehicle.current_mileage - last_service.mileage
                if miles_since >= interval:
                    alerts.append({"level": "MODERATE", "rule": f"mileage_{rule_key.replace(' ', '_')}", "message": f"{vehicle.nickname}: {service_keyword.title()} due. {miles_since:,} miles since last service (interval: every {interval:,} miles)."})
            else:
                alerts.append({"level": "LOW", "rule": f"no_record_{rule_key.replace(' ', '_')}", "message": f"{vehicle.nickname}: No {service_keyword} record with mileage found. Log one to enable mileage-based reminders."})

        last_any = db.query(models.MaintenanceRecord).filter(
            models.MaintenanceRecord.vehicle_id == vehicle.id
        ).order_by(models.MaintenanceRecord.service_date.desc()).first()
        if not last_any or last_any.service_date < now - timedelta(days=time_gap_days):
            days_since = (now - last_any.service_date).days if last_any else "unknown"
            alerts.append({"level": "LOW", "rule": "maintenance_time_gap", "message": f"{vehicle.nickname}: No maintenance logged in over {time_gap_days} days (last service: {days_since} days ago)."})

    return {"alert_count": len(alerts), "alerts": alerts, "generated_at": now.isoformat()}


#TEST DATA SEEDER

@app.post("/dev/seed-overdue")
def seed_overdue_services(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.user_id == current_user.id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Add a vehicle first before seeding test data.")
    old_date = datetime.utcnow() - timedelta(days=120)
    vehicle.current_mileage = (vehicle.current_mileage or 0) + 25000
    for service, miles_back in [("Oil & Filter Change", 6000), ("Tire Rotation", 9000), ("Brake Inspection", 22000)]:
        db.add(models.MaintenanceRecord(vehicle_id=vehicle.id, service_type=service, mileage=vehicle.current_mileage - miles_back, service_date=old_date, notes="[Test data - seeded for alert preview]"))
    completed_trip = db.query(models.Trip).join(models.Vehicle).filter(models.Vehicle.user_id == current_user.id, models.Trip.end_time.isnot(None)).first()
    if completed_trip:
        for sev in [8, 7, 6]:
            db.add(models.SafetyIncident(trip_id=completed_trip.id, severity=sev, description="[Test data - seeded for alert preview]", created_at=datetime.utcnow() - timedelta(days=3)))
    db.commit()
    return {"seeded": True, "vehicle": vehicle.nickname, "new_mileage": vehicle.current_mileage, "note": "Check Dashboard for alerts."}


@app.delete("/dev/clear-test-data")
def clear_test_data(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    deleted_m = db.query(models.MaintenanceRecord).join(models.Vehicle).filter(
        models.Vehicle.user_id == current_user.id,
        models.MaintenanceRecord.notes.like("%Test data%"),
    ).all()
    deleted_i = db.query(models.SafetyIncident).join(models.Trip).join(models.Vehicle).filter(
        models.Vehicle.user_id == current_user.id,
        models.SafetyIncident.description.like("%Test data%"),
    ).all()
    for r in deleted_m: db.delete(r)
    for i in deleted_i: db.delete(i)
    db.commit()
    return {"deleted_maintenance": len(deleted_m), "deleted_incidents": len(deleted_i)}


#CSV EXPORT

def _csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    output = io.StringIO()
    if not rows:
        output.write("no data\n")
    else:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.get("/export/trips")
def export_trips(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    trips = db.query(models.Trip).join(models.Vehicle).filter(models.Vehicle.user_id == current_user.id).order_by(models.Trip.id).all()
    rows = [{"id": t.id, "vehicle_id": t.vehicle_id, "start_label": t.start_label, "end_label": t.end_label, "start_time": t.start_time, "end_time": t.end_time, "duration_minutes": t.duration_minutes} for t in trips]
    return _csv_response(rows, "itereta_trips.csv")


@app.get("/export/safety")
def export_safety(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    incidents = db.query(models.SafetyIncident).join(models.Trip).join(models.Vehicle).filter(models.Vehicle.user_id == current_user.id).order_by(models.SafetyIncident.id).all()
    rows = [{"id": i.id, "trip_id": i.trip_id, "severity": i.severity, "description": i.description, "created_at": i.created_at} for i in incidents]
    return _csv_response(rows, "itereta_safety.csv")


@app.get("/export/maintenance")
def export_maintenance(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    records = db.query(models.MaintenanceRecord).join(models.Vehicle).filter(models.Vehicle.user_id == current_user.id).order_by(models.MaintenanceRecord.id).all()
    rows = [{"id": r.id, "vehicle_id": r.vehicle_id, "service_type": r.service_type, "cost": r.cost, "mileage": r.mileage, "service_date": r.service_date, "notes": r.notes} for r in records]
    return _csv_response(rows, "itereta_maintenance.csv")