from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class TimeRange(BaseModel):
    start_time: datetime
    end_time: datetime


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=1000)


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class HealthCheckResponse(BaseModel):
    service: str
    status: HealthStatus
    response_time: Optional[float] = None
    error: Optional[str] = None
    timestamp: datetime


class SystemHealthResponse(BaseModel):
    overall_status: HealthStatus
    services: List[HealthCheckResponse]
    timestamp: datetime
