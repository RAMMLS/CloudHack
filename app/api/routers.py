from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from app.models.kubernetes_models import *
from app.models.metrics_models import *
from app.models.incident_models import *
from app.models.common_models import *
from app.services.kubernetes_client import KubernetesClient
from app.services.prometheus_client import PrometheusClient
from app.services.loki_client import LokiClient
from app.services.jaeger_client import JaegerClient
from app.services.incident_analyzer import IncidentAnalyzer
from app.services.health_check import HealthCheckService
from app.services.metrics_collector import MetricsCollector

# Create routers
kubernetes_router = APIRouter(prefix="/kubernetes")
metrics_router = APIRouter(prefix="/metrics")
logs_router = APIRouter(prefix="/logs")
traces_router = APIRouter(prefix="/traces")
analysis_router = APIRouter(prefix="/analysis")
health_router = APIRouter(prefix="/health")
incidents_router = APIRouter(prefix="/incidents")

# Service instances
k8s_client = KubernetesClient()
prometheus_client = PrometheusClient()
loki_client = LokiClient()
jaeger_client = JaegerClient()
incident_analyzer = IncidentAnalyzer()
health_service = HealthCheckService()
metrics_collector = MetricsCollector()


# Kubernetes Routes
@kubernetes_router.get("/cluster/info", response_model=Dict[str, Any])
async def get_cluster_info():
    """Get cluster information"""
    try:
        return await k8s_client.get_cluster_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@kubernetes_router.get("/nodes", response_model=List[Dict[str, Any]])
async def get_nodes():
    """Get all nodes in the cluster"""
    try:
        return await k8s_client.get_nodes()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@kubernetes_router.get("/pods", response_model=List[Dict[str, Any]])
async def get_pods(namespace: Optional[str] = None):
    """Get pods in the cluster"""
    try:
        return await k8s_client.get_pods(namespace)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@kubernetes_router.get("/deployments", response_model=List[Dict[str, Any]])
async def get_deployments(namespace: Optional[str] = None):
    """Get deployments in the cluster"""
    try:
        return await k8s_client.get_deployments(namespace)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@kubernetes_router.get("/services", response_model=List[Dict[str, Any]])
async def get_services(namespace: Optional[str] = None):
    """Get services in the cluster"""
    try:
        return await k8s_client.get_services(namespace)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@kubernetes_router.get("/events", response_model=List[Dict[str, Any]])
async def get_events(namespace: Optional[str] = None, limit: int = 100):
    """Get recent events in the cluster"""
    try:
        events = await k8s_client.get_events(namespace)
        return events[:limit]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@kubernetes_router.get("/namespaces", response_model=List[Dict[str, Any]])
async def get_namespaces():
    """Get all namespaces"""
    try:
        return await k8s_client.get_namespaces()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Metrics Routes
@metrics_router.post("/query", response_model=List[MetricResponse])
async def query_metrics(query: MetricQuery):
    """Execute Prometheus query"""
    try:
        if query.start_time and query.end_time:
            results = await prometheus_client.query_range(
                query=query.query,
                start_time=query.start_time.isoformat(),
                end_time=query.end_time.isoformat(),
                step=query.step
            )
        else:
            results = await prometheus_client.query(query.query)
        
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@metrics_router.get("/alerts", response_model=List[Dict[str, Any]])
async def get_alerts():
    """Get firing alerts"""
    try:
        return await prometheus_client.check_alerts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@metrics_router.get("/cluster/summary", response_model=Dict[str, Any])
async def get_cluster_metrics_summary():
    """Get cluster metrics summary"""
    try:
        return await prometheus_client.get_cluster_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@metrics_router.get("/collector/summary", response_model=Dict[str, Any])
async def get_collector_summary():
    """Get metrics collector summary"""
    try:
        return await metrics_collector.get_metrics_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@metrics_router.get("/anomalies", response_model=List[Dict[str, Any]])
async def get_anomalies(hours: int = 24):
    """Get recent anomalies"""
    try:
        return await metrics_collector.get_anomalies(hours)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Logs Routes
@logs_router.get("/query", response_model=List[Dict[str, Any]])
async def query_logs(
    query: str = Query(..., description="Loki query"),
    limit: int = Query(100, description="Number of log entries"),
    hours: int = Query(1, description="Time range in hours")
):
    """Query logs using Loki"""
    try:
        start_time = datetime.utcnow() - timedelta(hours=hours)
        return await loki_client.query_logs(query, limit, start_time)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@logs_router.get("/pod/{pod_name}", response_model=List[Dict[str, Any]])
async def get_pod_logs(
    pod_name: str,
    namespace: str = "default",
    container: Optional[str] = None,
    tail_lines: int = 100
):
    """Get logs for a specific pod"""
    try:
        return await loki_client.get_pod_logs(pod_name, namespace, container, tail_lines)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@logs_router.get("/errors", response_model=Dict[str, Any])
async def get_error_logs(
    namespace: Optional[str] = None,
    hours: int = 1
):
    """Get error logs"""
    try:
        return await loki_client.search_errors(namespace, f"{hours}h")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@logs_router.get("/patterns", response_model=Dict[str, Any])
async def get_log_patterns(
    namespace: Optional[str] = None,
    hours: int = 24
):
    """Analyze log patterns"""
    try:
        return await loki_client.get_log_patterns(namespace, f"{hours}h")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Traces Routes
@traces_router.get("/services", response_model=List[str])
async def get_traced_services():
    """Get list of services with tracing"""
    try:
        return await jaeger_client.get_services()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@traces_router.get("/service/{service_name}", response_model=List[Dict[str, Any]])
async def get_service_traces(
    service_name: str,
    hours: int = 1,
    limit: int = 100
):
    """Get traces for a service"""
    try:
        return await jaeger_client.get_traces(service_name, f"{hours}h", limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@traces_router.get("/trace/{trace_id}", response_model=Dict[str, Any])
async def get_trace_detail(trace_id: str):
    """Get detailed trace information"""
    try:
        return await jaeger_client.get_trace_detail(trace_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@traces_router.get("/latency/{service_name}", response_model=Dict[str, Any])
async def analyze_latency(service_name: str, hours: int = 1):
    """Analyze latency for a service"""
    try:
        return await jaeger_client.analyze_latency(service_name, f"{hours}h")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@traces_router.get("/dependencies", response_model=Dict[str, Any])
async def get_service_dependencies():
    """Get service dependencies"""
    try:
        return await jaeger_client.get_dependencies()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Analysis Routes
@analysis_router.post("/incident", response_model=Dict[str, Any])
async def analyze_incident(symptoms: Dict[str, Any]):
    """Analyze incident symptoms and provide diagnosis"""
    try:
        return await incident_analyzer.analyze_incident(symptoms)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@analysis_router.get("/cluster/health", response_model=Dict[str, Any])
async def get_cluster_health_analysis():
    """Get comprehensive cluster health analysis"""
    try:
        return await health_service.check_kubernetes_cluster_health()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Health Routes
@health_router.get("/", response_model=SystemHealthResponse)
async def health_check():
    """Health check for all services"""
    try:
        return await health_service.check_all_services()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@health_router.get("/kubernetes", response_model=Dict[str, Any])
async def kubernetes_health():
    """Kubernetes cluster health check"""
    try:
        return await health_service.check_kubernetes_cluster_health()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Incidents Routes
@incidents_router.get("/", response_model=List[Incident])
async def get_incidents(limit: int = 50):
    """Get recent incidents (mock implementation)"""
    # This would typically query a database
    return []

@incidents_router.post("/", response_model=Incident)
async def create_incident(incident: IncidentCreate):
    """Create a new incident (mock implementation)"""
    # This would typically save to a database
    return Incident(
        id="inc-001",
        title=incident.title,
        description=incident.description,
        severity=incident.severity,
        status="open",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        affected_services=incident.affected_services
    )

@incidents_router.get("/{incident_id}/action-plan", response_model=ActionPlan)
async def get_incident_action_plan(incident_id: str):
    """Get action plan for an incident (mock implementation)"""
    return ActionPlan(
        incident_id=incident_id,
        steps=[
            {
                "step": 1,
                "action": "Investigate the root cause",
                "estimated_duration": 15,
                "critical": True
            }
        ],
        estimated_duration=15,
        risk_level="medium",
        prerequisites=["Access to monitoring tools", "Understanding of the system"]
    )
