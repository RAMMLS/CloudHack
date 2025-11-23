import logging
from typing import List, Dict, Any, Optional
import httpx
from prometheus_api_client import PrometheusConnect
from app.config import settings

logger = logging.getLogger(__name__)


class PrometheusClient:
    def __init__(self):
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        try:
            self._client = PrometheusConnect(
                url=settings.prometheus_url,
                disable_ssl=True
            )
            logger.info("Prometheus client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Prometheus client: {e}")
            raise

    async def query(self, query: str, time: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            if time:
                result = self._client.custom_query(query=query, params={"time": time})
            else:
                result = self._client.custom_query(query=query)
            
            return result
        except Exception as e:
            logger.error(f"Error executing Prometheus query: {e}")
            raise

    async def query_range(self, query: str, start_time: str, end_time: str, step: str = "15s") -> List[Dict[str, Any]]:
        try:
            result = self._client.custom_query_range(
                query=query,
                start_time=start_time,
                end_time=end_time,
                step=step
            )
            return result
        except Exception as e:
            logger.error(f"Error executing Prometheus range query: {e}")
            raise

    async def get_metric_metadata(self, metric_name: str) -> List[Dict[str, Any]]:
        try:
            metadata = self._client.get_metric_metadata(metric_name=metric_name)
            return metadata
        except Exception as e:
            logger.error(f"Error getting metric metadata: {e}")
            raise

    async def get_all_metrics(self) -> List[str]:
        try:
            metrics = self._client.all_metrics()
            return metrics
        except Exception as e:
            logger.error(f"Error getting all metrics: {e}")
            raise

    async def get_cluster_metrics(self) -> Dict[str, Any]:
        try:
            # Node metrics
            node_cpu_query = '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
            node_memory_query = '100 * (1 - ((node_memory_MemAvailable_bytes) / (node_memory_MemTotal_bytes)))'
            node_disk_query = '100 * (1 - ((node_filesystem_avail_bytes{mountpoint="/"}) / (node_filesystem_size_bytes{mountpoint="/"})))'
            
            cpu_usage = await self.query(node_cpu_query)
            memory_usage = await self.query(node_memory_query)
            disk_usage = await self.query(node_disk_query)
            
            # Pod metrics
            pod_count_query = 'count(kube_pod_info)'
            pod_restarts_query = 'sum(kube_pod_container_status_restarts_total) by (namespace)'
            
            pod_count = await self.query(pod_count_query)
            pod_restarts = await self.query(pod_restarts_query)
            
            return {
                "node_metrics": {
                    "cpu_usage": cpu_usage,
                    "memory_usage": memory_usage,
                    "disk_usage": disk_usage
                },
                "pod_metrics": {
                    "total_pods": pod_count,
                    "restarts_by_namespace": pod_restarts
                }
            }
        except Exception as e:
            logger.error(f"Error getting cluster metrics: {e}")
            raise

    async def check_alerts(self) -> List[Dict[str, Any]]:
        try:
            alerts_query = 'ALERTS{alertstate="firing"}'
            alerts = await self.query(alerts_query)
            
            alert_list = []
            for alert in alerts:
                alert_list.append({
                    "name": alert["metric"].get("alertname"),
                    "severity": alert["metric"].get("severity"),
                    "state": alert["metric"].get("alertstate"),
                    "instance": alert["metric"].get("instance"),
                    "job": alert["metric"].get("job"),
                    "value": alert["value"][1] if "value" in alert else None
                })
            
            return alert_list
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
            raise
