from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# SQLite needs connect_args for threading; PostgreSQL uses connection pooling
db_url = settings.database_url

# Vercel has read-only filesystem, use /tmp for SQLite
if db_url.startswith("sqlite") and "/tmp/" not in db_url:
    db_url = "sqlite:////tmp/ecom_agent.db"

connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
