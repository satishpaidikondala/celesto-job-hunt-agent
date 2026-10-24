import os
import logging
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone

logger = logging.getLogger("ledger.db")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ledger:ledger@ledger:5432/ledger")

# Handle PostgreSQL vs SQLite engine parameters
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
except Exception as e:
    logger.warning(f"Could not connect to {DATABASE_URL}: {e}. Falling back to SQLite.")
    engine = create_engine("sqlite:///./ledger.db", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class RunModel(Base):
    __tablename__ = "runs"

    run_id = Column(String(128), primary_key=True, index=True)
    sandbox_name = Column(String(128), unique=True, nullable=False, index=True)
    problem_id = Column(String(128), nullable=False)
    state = Column(String(64), nullable=False)
    execution_target = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    Base.metadata.create_all(bind=engine)
    # Seed default row if table is empty or row does not exist
    db = SessionLocal()
    try:
        existing = db.query(RunModel).filter_by(sandbox_name="sbx-seeddemo1").first()
        if not existing:
            seed_run = RunModel(
                run_id="run-seeddemo1",
                sandbox_name="sbx-seeddemo1",
                problem_id="job-hunt-research",
                state="deleted",
                execution_target="celesto_sandbox",
                created_at=datetime.now(timezone.utc)
            )
            db.add(seed_run)
            db.commit()
    except Exception as e:
        logger.error(f"Error seeding DB: {e}")
        db.rollback()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Ensure database tables and initial seed exist upon import
init_db()
