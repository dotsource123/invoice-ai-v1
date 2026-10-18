import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Use Render's persistent disk when configured.
BASE_DIR = Path(__file__).resolve().parent

DB_PATH = Path(
    os.getenv("SQLITE_DB_PATH", str(BASE_DIR / "invoices.db"))
).resolve()

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()
