import os
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import init_db, get_db, RunModel
from app.schemas import RunCreate, RunResponse, ALLOWED_STATES, SANDBOX_NAME_REGEX


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables and seed rows exist on startup
    init_db()
    yield


app = FastAPI(
    title="Celesto Run Ledger API",
    description="Control plane HTTP API recording AI agent runs executed inside Celesto sandboxes",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static file directories so docker-compose up serves the generated report files
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

if os.path.exists("reports"):
    app.mount("/reports", StaticFiles(directory="reports"), name="reports")
if os.path.exists("logs"):
    app.mount("/logs", StaticFiles(directory="logs"), name="logs")



@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Ensure all request validation errors return HTTP 400 instead of default 422,
    as required by the hackathon ledger specification.
    """
    errors = exc.errors()
    error_messages = [f"{err.get('loc', [])}: {err.get('msg', '')}" for err in errors]
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Bad Request", "errors": error_messages}
    )


@app.get("/health", status_code=status.HTTP_200_OK)
def get_health():
    """Healthcheck endpoint for Docker Compose and container probes."""
    return {"status": "ok"}


@app.get("/api/runs", response_model=List[RunResponse], status_code=status.HTTP_200_OK)
def list_runs(db: Session = Depends(get_db)):
    """List all recorded sandbox runs in the ledger."""
    runs = db.query(RunModel).order_by(RunModel.created_at.asc()).all()
    return runs


@app.post("/api/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def create_run(run_in: RunCreate, db: Session = Depends(get_db)):
    """
    Record an agent run executed inside a Celesto sandbox.
    Rejects any execution target other than celesto_sandbox with HTTP 400.
    """
    # Double check domain constraints in handler
    if run_in.execution_target != "celesto_sandbox":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Execution target must be 'celesto_sandbox', got '{run_in.execution_target}'"
        )

    if run_in.state not in ALLOWED_STATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state '{run_in.state}'. Allowed: {sorted(ALLOWED_STATES)}"
        )

    if not SANDBOX_NAME_REGEX.match(run_in.sandbox_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sandbox_name '{run_in.sandbox_name}'. Must match '^sbx-[a-z0-9]{{8,}}$'"
        )

    # Check for duplicate sandbox name or run_id
    existing = db.query(RunModel).filter_by(sandbox_name=run_in.sandbox_name).first()
    if existing:
        # Update existing record state or raise conflict
        existing.state = run_in.state
        existing.problem_id = run_in.problem_id
        db.commit()
        db.refresh(existing)
        return existing

    new_run = RunModel(
        run_id=run_in.run_id,
        sandbox_name=run_in.sandbox_name,
        problem_id=run_in.problem_id,
        state=run_in.state,
        execution_target=run_in.execution_target
    )
    db.add(new_run)
    db.commit()
    db.refresh(new_run)
    return new_run


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8080"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
