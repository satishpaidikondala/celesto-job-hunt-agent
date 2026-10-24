import re
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict


ALLOWED_STATES = {"created", "ready", "running", "succeeded", "failed", "deleted"}
SANDBOX_NAME_REGEX = re.compile(r"^sbx-[a-z0-9]{8,}$")


class RunCreate(BaseModel):
    run_id: str = Field(..., min_length=1)
    sandbox_name: str
    problem_id: str = Field(..., min_length=1)
    state: str
    execution_target: str

    @field_validator("sandbox_name")
    @classmethod
    def validate_sandbox_name(cls, v: str) -> str:
        if not SANDBOX_NAME_REGEX.match(v):
            raise ValueError(f"sandbox_name '{v}' does not match pattern '^sbx-[a-z0-9]{{8,}}$'")
        return v

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        if v not in ALLOWED_STATES:
            raise ValueError(f"state '{v}' is not in allowed states: {sorted(ALLOWED_STATES)}")
        return v

    @field_validator("execution_target")
    @classmethod
    def validate_execution_target(cls, v: str) -> str:
        if v != "celesto_sandbox":
            raise ValueError(f"execution_target must be 'celesto_sandbox', got '{v}'")
        return v


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    sandbox_name: str
    problem_id: str
    state: str
    execution_target: str
    created_at: Optional[datetime] = None

