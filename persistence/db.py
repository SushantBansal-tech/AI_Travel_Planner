from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./booking.db")

# For SQLite, check_same_thread=False is required for multithreaded web servers
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def init_db():
    # Import models here so they get registered with Base before creating tables
    import persistence.models  # noqa: F401
    Base.metadata.create_all(bind=engine)