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

pool_kwargs = {
    "connect_args": connect_args,
    "pool_pre_ping": True,
}

# PostgreSQL: use connection pooling for concurrent requests
if not db_url.startswith("sqlite"):
    pool_kwargs.update({
        "pool_size": 10,         # 10 persistent connections
        "max_overflow": 20,      # 20 extra during burst = 30 total
        "pool_timeout": 30,      # Wait 30s for connection before error
        "pool_recycle": 300,     # Recycle connections every 5 min
    })

engine = create_engine(db_url, **pool_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
