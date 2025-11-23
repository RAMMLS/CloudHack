from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from app.models.common_models import Severity


class MetricQuery(BaseModel):
    query: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    step: Optional[str] = "15s"


class MetricResponse(BaseModel):
    metric: Dict[str, str]
    values: List[List[Union[int, str]]]
    value: Optional[List[Union[int, str]]]


class AlertRule(BaseModel):
    name: str
    query: str
    duration: str
    severity: Severity
    summary: str
    description: str
    labels: Dict[str, str]
    annotations: Dict[str, str]


class AnomalyDetection(BaseModel):
    metric_name: str
    algorithm: str
    sensitivity: float
    window_size: int


class MetricAnalysis(BaseModel):
    metric_name: str
    current_value: float
    average_value: float
    trend: str
    anomaly_score: float
    recommendations: List[str]
