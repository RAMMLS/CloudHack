from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from app.models.common_models import Severity, HealthStatus


class PodStatus(BaseModel):
    name: str
    namespace: str
    status: str
    ready: str
    restarts: int
    age: str
    node: str
    ip: str
    created_at: datetime


class NodeStatus(BaseModel):
    name: str
    status: str
    roles: List[str]
    age: str
    version: str
    internal_ip: str
    external_ip: Optional[str]
    cpu_usage: float
    memory_usage: float
    pod_capacity: int
    pod_allocatable: int
    conditions: List[Dict[str, Any]]


class DeploymentStatus(BaseModel):
    name: str
    namespace: str
    ready: str
    up_to_date: int
    available: int
    age: str
    strategy: str


class ServiceStatus(BaseModel):
    name: str
    namespace: str
    type: str
    cluster_ip: str
    external_ip: Optional[str]
    ports: List[str]
    age: str
    selector: Dict[str, str]


class IngressStatus(BaseModel):
    name: str
    namespace: str
    hosts: List[str]
    addresses: List[str]
    ports: List[str]
    age: str


class Event(BaseModel):
    name: str
    namespace: str
    type: str
    reason: str
    message: str
    count: int
    first_seen: datetime
    last_seen: datetime
    involved_object: Dict[str, str]


class ResourceUsage(BaseModel):
    cpu_usage: float
    memory_usage: float
    storage_usage: Optional[float]
    network_rx: Optional[float]
    network_tx: Optional[float]


class KubernetesHealth(BaseModel):
    cluster_name: str
    overall_status: HealthStatus
    nodes_healthy: int
    nodes_total: int
    pods_healthy: int
    pods_total: int
    issues: List[Dict[str, Any]]
    last_check: datetime
