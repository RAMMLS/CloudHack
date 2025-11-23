from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from app.models.common_models import Severity


class Incident(BaseModel):
    id: str
    title: str
    description: str
    severity: Severity
    status: str
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    affected_services: List[str]
    root_cause: Optional[str]
    actions_taken: List[str]
    next_steps: List[str]


class IncidentCreate(BaseModel):
    title: str
    description: str
    severity: Severity
    affected_services: List[str]


class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    root_cause: Optional[str] = None
    actions_taken: Optional[List[str]] = None
    next_steps: Optional[List[str]] = None


class ActionPlan(BaseModel):
    incident_id: str
    steps: List[Dict[str, Any]]
    estimated_duration: int
    risk_level: str
    prerequisites: List[str]
