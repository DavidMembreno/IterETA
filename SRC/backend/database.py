from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Always resolve relative to this file's location (SRC/backend/database.py)
BASE_DIR = Path(__file__).resolve().parent  # .../SRC/backend
DB_PATH = (BASE_DIR.parent / "database" / "itereta.db").resolve()  # .../SRC/database/itereta.db

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()