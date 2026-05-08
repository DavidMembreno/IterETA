# IterETA

**Personal Transportation Reliability and Vehicle Operations Platform**

IterETA is a personal transportation reliability tool built for commuter students and daily drivers. Rather than handling navigation directly, it focuses on what existing map apps lack: history-based ETA estimation, safety incident tracking, vehicle maintenance planning, and reliability analytics. All data is private to each user account and stored locally.

## Features

**History-based ETA** uses your own past trip data to estimate travel time for repeated routes, with a conservative buffer and a confidence rating based on sample size.

**Trip logging** lets you start and end trips with labeled locations. Duration is calculated automatically, and any trip in progress is recovered if the page is reloaded mid-trip.

**Safety incident tracking** lets you log incidents after trips using a 1 to 10 severity scale. Rule-based alerts fire for high severity events, frequency spikes, and trend escalation.

**Maintenance records** track service history per vehicle with mileage and cost. Alerts fire when configured service intervals are exceeded.

**Reliability analytics** show completion rate, average trip duration, and 30-day incident summaries across all your vehicles.

**CSV export** lets you download your trip, safety, and maintenance data for external analysis.

**Multi-user accounts** provide full registration and login with bcrypt password hashing and session token authentication. Each user's data is completely isolated.

**Dark mode** is available via a toggle in the app header.

**Launch animation** plays a custom splash screen featuring a hand-drawn car asset when the app first loads.

## Tech Stack

**Backend** is Python, FastAPI, SQLAlchemy, and SQLite. Passwords are hashed with bcrypt. The backend test suite uses pytest and covers 65 tests, all passing.

**Frontend** is React, Vite, TypeScript, and Tailwind CSS. Axios handles all HTTP requests with a request interceptor that attaches the session token automatically.

## Project Structure

```
SRC/
    backend/
        main.py         API routes and business logic
        models.py       SQLAlchemy ORM models
        schemas.py      Pydantic validation schemas
        database.py     Engine, session, and base config
    database/
        itereta.db      SQLite database file
    frontend/
        public/
            car.png     Hand-drawn launch animation asset
        src/
            App.tsx     Main application component
            Splash.tsx  Launch animation component
    tests/
        test_main.py    Full pytest backend test suite
    requirements.txt    Python dependencies
    ReadMe.md
```

## Setup and Running Locally

**Prerequisites** are Python 3.10 or higher and Node.js 18 or higher.

**Backend setup:**

```bash
cd SRC
python -m venv .venv
```

On Windows:
```bash
.venv\Scripts\Activate.ps1
```

On macOS or Linux:
```bash
source .venv/bin/activate
```

Then install dependencies and start the server:
```bash
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The API runs at http://localhost:8000 and interactive docs are at http://localhost:8000/docs.

**Frontend setup:**

```bash
cd SRC/frontend
npm install
npm run dev
```

The app runs at http://localhost:5173.

The API base URL is hardcoded in App.tsx. Update the API constant at the top of that file if your backend is running on a different host or port.

## Running Tests

From inside SRC with the virtual environment active:

```bash
python -m pytest tests/test_main.py -v
```

The suite covers authentication, vehicles, trips, safety incidents, maintenance records, ETA logic, alerts, settings, analytics, and CSV exports.

## Environment Notes

Dependencies are managed via requirements.txt generated from the active virtual environment. If the environment is ever lost or corrupted, restoring it only requires:

```bash
python -m venv .venv
pip install -r requirements.txt
```

This file was added after the virtual environment was accidentally deleted during development, which made clear the project needed explicit dependency documentation.

## ETA Methodology

ETA estimates are derived entirely from the user's own historical trip data for a given route. The system computes a mean duration and adds a standard deviation buffer for the conservative estimate. Confidence is rated low, moderate, or high based on trip count. This probe-data approach aligns with established methodology in transportation research, where ground truth probe vehicle data is treated as the accuracy benchmark for travel time estimation (Kothuri et al., 2008).

## Known Limitations

SQLite is not suited for hosted multi-user deployment. A PostgreSQL migration would be required for Railway or a similar platform. The API base URL is hardcoded and must be updated manually for different network environments. ETA accuracy improves with more trips on the same route and low confidence estimates with only one or two data points should be treated as rough references.

## Author

David Membreno, California Lutheran University, CSC 499 Capstone
Supervised by Dr. Chang-Shyh Peng