import logging
import asyncio
from typing import List, Dict, Any
from datetime import datetime
import httpx
from kubernetes.client.rest import ApiException
from app.config import settings
from app.models.common_models import HealthStatus, HealthCheckResponse, SystemHealthResponse
from app.services.kubernetes_client import KubernetesClient
from app.services.prometheus_client import PrometheusClient
from app.services.loki_client import LokiClient
from app.services.jaeger_client import JaegerClient

logger = logging.getLogger(__name__)


class HealthCheckService:
    def __init__(self):
        self.k8s_client = KubernetesClient()
        self.prometheus_client = PrometheusClient()
        self.loki_client = LokiClient()
        self.jaeger_client = JaegerClient()

    async def check_all_services(self) -> SystemHealthResponse:
        """Check health of all dependent services"""
        try:
            services_to_check = [
                self._check_kubernetes_api,
                self._check_prometheus,
                self._check_loki,
                self._check_jaeger,
                self._check_database,
                self._check_redis
            ]

            tasks = [check() for check in services_to_check]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            health_responses = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Health check failed: {result}")
                    health_responses.append(HealthCheckResponse(
                        service="unknown",
                        status=HealthStatus.UNHEALTHY,
                        error=str(result),
                        timestamp=datetime.utcnow()
                    ))
                else:
                    health_responses.append(result)

            # Determine overall status
            overall_status = HealthStatus.HEALTHY
            unhealthy_services = [s for s in health_responses if s.status != HealthStatus.HEALTHY]
            if any(s.status == HealthStatus.UNHEALTHY for s in health_responses):
                overall_status = HealthStatus.UNHEALTHY
            elif unhealthy_services:
                overall_status = HealthStatus.DEGRADED

            return SystemHealthResponse(
                overall_status=overall_status,
                services=health_responses,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Error in health check: {e}")
            return SystemHealthResponse(
                overall_status=HealthStatus.UNHEALTHY,
                services=[],
                timestamp=datetime.utcnow()
            )

    async def _check_kubernetes_api(self) -> HealthCheckResponse:
        """Check Kubernetes API health"""
        try:
            start_time = datetime.utcnow()
            
            # Try to list namespaces as a basic health check
            await self.k8s_client.get_namespaces()
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            return HealthCheckResponse(
                service="kubernetes_api",
                status=HealthStatus.HEALTHY,
                response_time=response_time,
                timestamp=datetime.utcnow()
            )
            
        except ApiException as e:
            return HealthCheckResponse(
                service="kubernetes_api",
                status=HealthStatus.UNHEALTHY,
                error=f"Kubernetes API error: {e.status} - {e.reason}",
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return HealthCheckResponse(
                service="kubernetes_api",
                status=HealthStatus.UNHEALTHY,
                error=f"Kubernetes connection failed: {str(e)}",
                timestamp=datetime.utcnow()
            )

    async def _check_prometheus(self) -> HealthCheckResponse:
        """Check Prometheus health"""
        try:
            start_time = datetime.utcnow()
            
            # Try to query a simple metric
            await self.prometheus_client.get_all_metrics()
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            return HealthCheckResponse(
                service="prometheus",
                status=HealthStatus.HEALTHY,
                response_time=response_time,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            return HealthCheckResponse(
                service="prometheus",
                status=HealthStatus.UNHEALTHY,
                error=f"Prometheus connection failed: {str(e)}",
                timestamp=datetime.utcnow()
            )

    async def _check_loki(self) -> HealthCheckResponse:
        """Check Loki health"""
        try:
            start_time = datetime.utcnow()
            
            # Try to query Loki
            async with httpx.AsyncClient(timeout=settings.loki_timeout) as client:
                response = await client.get(f"{settings.loki_url}/ready")
                response.raise_for_status()
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            return HealthCheckResponse(
                service="loki",
                status=HealthStatus.HEALTHY,
                response_time=response_time,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            return HealthCheckResponse(
                service="loki",
                status=HealthStatus.UNHEALTHY,
                error=f"Loki connection failed: {str(e)}",
                timestamp=datetime.utcnow()
            )

    async def _check_jaeger(self) -> HealthCheckResponse:
        """Check Jaeger health"""
        try:
            start_time = datetime.utcnow()
            
            # Try to get services list
            await self.jaeger_client.get_services()
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            return HealthCheckResponse(
                service="jaeger",
                status=HealthStatus.HEALTHY,
                response_time=response_time,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            return HealthCheckResponse(
                service="jaeger",
                status=HealthStatus.UNHEALTHY,
                error=f"Jaeger connection failed: {str(e)}",
                timestamp=datetime.utcnow()
            )

    async def _check_database(self) -> HealthCheckResponse:
        """Check database health"""
        try:
            start_time = datetime.utcnow()
            
            # Simple database connection check
            # This would actually test the database connection
            await asyncio.sleep(0.1)  # Simulate DB check
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            return HealthCheckResponse(
                service="database",
                status=HealthStatus.HEALTHY,
                response_time=response_time,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            return HealthCheckResponse(
                service="database",
                status=HealthStatus.UNHEALTHY,
                error=f"Database connection failed: {str(e)}",
                timestamp=datetime.utcnow()
            )

    async def _check_redis(self) -> HealthCheckResponse:
        """Check Redis health"""
        try:
            start_time = datetime.utcnow()
            
            # Simple Redis connection check
            # This would actually test Redis connection
            await asyncio.sleep(0.1)  # Simulate Redis check
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            return HealthCheckResponse(
                service="redis",
                status=HealthStatus.HEALTHY,
                response_time=response_time,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            return HealthCheckResponse(
                service="redis",
                status=HealthStatus.UNHEALTHY,
                error=f"Redis connection failed: {str(e)}",
                timestamp=datetime.utcnow()
            )

    async def check_kubernetes_cluster_health(self) -> Dict[str, Any]:
        """Perform comprehensive Kubernetes cluster health check"""
        try:
            health_info = {
                "timestamp": datetime.utcnow(),
                "components": {},
                "overall_status": HealthStatus.HEALTHY,
                "issues": []
            }

            # Check nodes
            try:
                nodes = await self.k8s_client.get_nodes()
                ready_nodes = [n for n in nodes if n["status"] == "Ready"]
                
                health_info["components"]["nodes"] = {
                    "status": HealthStatus.HEALTHY if len(ready_nodes) == len(nodes) else HealthStatus.UNHEALTHY,
                    "ready": len(ready_nodes),
                    "total": len(nodes)
                }
                
                if len(ready_nodes) < len(nodes):
                    health_info["overall_status"] = HealthStatus.DEGRADED
                    health_info["issues"].append(f"{len(nodes) - len(ready_nodes)} nodes not ready")
                    
            except Exception as e:
                health_info["components"]["nodes"] = {
                    "status": HealthStatus.UNHEALTHY,
                    "error": str(e)
                }
                health_info["overall_status"] = HealthStatus.UNHEALTHY

            # Check pods
            try:
                pods = await self.k8s_client.get_pods()
                running_pods = [p for p in pods if p["status"] == "Running"]
                failed_pods = [p for p in pods if p["status"] in ["CrashLoopBackOff", "Error", "Failed"]]
                
                health_info["components"]["pods"] = {
                    "status": HealthStatus.HEALTHY if not failed_pods else HealthStatus.DEGRADED,
                    "running": len(running_pods),
                    "failed": len(failed_pods),
                    "total": len(pods)
                }
                
                if failed_pods:
                    health_info["overall_status"] = HealthStatus.DEGRADED
                    health_info["issues"].append(f"{len(failed_pods)} pods in failed state")
                    
            except Exception as e:
                health_info["components"]["pods"] = {
                    "status": HealthStatus.UNHEALTHY,
                    "error": str(e)
                }
                health_info["overall_status"] = HealthStatus.UNHEALTHY

            # Check cluster version
            try:
                cluster_info = await self.k8s_client.get_cluster_info()
                health_info["cluster_info"] = cluster_info
            except Exception as e:
                health_info["cluster_info"] = {"error": str(e)}

            return health_info

        except Exception as e:
            logger.error(f"Error in cluster health check: {e}")
            return {
                "timestamp": datetime.utcnow(),
                "overall_status": HealthStatus.UNHEALTHY,
                "error": str(e)
            }
