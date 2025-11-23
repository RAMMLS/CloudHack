import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import psutil
from prometheus_api_client import PrometheusConnect
from app.config import settings
from app.services.kubernetes_client import KubernetesClient
from app.services.prometheus_client import PrometheusClient

logger = logging.getLogger(__name__)


class MetricsCollector:
    def __init__(self):
        self.prometheus_client = PrometheusClient()
        self.k8s_client = KubernetesClient()
        self._is_running = False
        self._collection_task = None
        self._collected_metrics = {}
        self._anomalies = []

    async def start(self):
        """Start background metrics collection"""
        self._is_running = True
        self._collection_task = asyncio.create_task(self._collect_metrics_loop())
        logger.info("Metrics collector started")

    async def stop(self):
        """Stop background metrics collection"""
        self._is_running = False
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
        logger.info("Metrics collector stopped")

    async def _collect_metrics_loop(self):
        """Main metrics collection loop"""
        while self._is_running:
            try:
                await self._collect_all_metrics()
                await asyncio.sleep(60)  # Collect every minute
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
                await asyncio.sleep(30)  # Wait before retry

    async def _collect_all_metrics(self):
        """Collect all types of metrics"""
        try:
            timestamp = datetime.utcnow()
            
            # Collect cluster-level metrics
            cluster_metrics = await self._collect_cluster_metrics()
            self._collected_metrics["cluster"] = {
                "timestamp": timestamp,
                "metrics": cluster_metrics
            }

            # Collect node metrics
            node_metrics = await self._collect_node_metrics()
            self._collected_metrics["nodes"] = {
                "timestamp": timestamp,
                "metrics": node_metrics
            }

            # Collect pod metrics
            pod_metrics = await self._collect_pod_metrics()
            self._collected_metrics["pods"] = {
                "timestamp": timestamp,
                "metrics": pod_metrics
            }

            # Check for anomalies
            await self._detect_anomalies()

            # Clean old data (keep last 6 hours)
            self._clean_old_metrics()

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

    async def _collect_cluster_metrics(self) -> Dict[str, Any]:
        """Collect cluster-level metrics"""
        try:
            # Cluster resource usage
            cluster_cpu_query = 'sum(rate(container_cpu_usage_seconds_total[5m])) / sum(kube_pod_container_resource_limits_cpu_cores) * 100'
            cluster_memory_query = 'sum(container_memory_working_set_bytes) / sum(kube_pod_container_resource_limits_memory_bytes) * 100'
            cluster_pod_query = 'count(kube_pod_info)'

            cluster_metrics = {}

            # CPU usage
            try:
                cpu_result = await self.prometheus_client.query(cluster_cpu_query)
                if cpu_result:
                    cluster_metrics["cpu_usage_percent"] = float(cpu_result[0]["value"][1])
            except Exception as e:
                logger.warning(f"Could not collect cluster CPU metrics: {e}")

            # Memory usage
            try:
                memory_result = await self.prometheus_client.query(cluster_memory_query)
                if memory_result:
                    cluster_metrics["memory_usage_percent"] = float(memory_result[0]["value"][1])
            except Exception as e:
                logger.warning(f"Could not collect cluster memory metrics: {e}")

            # Pod count
            try:
                pod_result = await self.prometheus_client.query(cluster_pod_query)
                if pod_result:
                    cluster_metrics["total_pods"] = int(pod_result[0]["value"][1])
            except Exception as e:
                logger.warning(f"Could not collect pod count metrics: {e}")

            # Node status
            try:
                nodes = await self.k8s_client.get_nodes()
                cluster_metrics["total_nodes"] = len(nodes)
                cluster_metrics["ready_nodes"] = sum(1 for node in nodes if node["status"] == "Ready")
            except Exception as e:
                logger.warning(f"Could not collect node status: {e}")

            return cluster_metrics

        except Exception as e:
            logger.error(f"Error collecting cluster metrics: {e}")
            return {}

    async def _collect_node_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Collect metrics for each node"""
        try:
            node_metrics = {}

            # Node CPU usage
            node_cpu_query = '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
            node_memory_query = '100 * (1 - ((node_memory_MemAvailable_bytes) / (node_memory_MemTotal_bytes)))'
            node_disk_query = '100 * (1 - ((node_filesystem_avail_bytes{mountpoint="/"}) / (node_filesystem_size_bytes{mountpoint="/"})))'

            cpu_results = await self.prometheus_client.query(node_cpu_query)
            memory_results = await self.prometheus_client.query(node_memory_query)
            disk_results = await self.prometheus_client.query(node_disk_query)

            # Parse CPU results
            for result in cpu_results:
                instance = result["metric"].get("instance", "").split(":")[0]
                if instance:
                    if instance not in node_metrics:
                        node_metrics[instance] = {}
                    node_metrics[instance]["cpu_usage_percent"] = float(result["value"][1])

            # Parse memory results
            for result in memory_results:
                instance = result["metric"].get("instance", "").split(":")[0]
                if instance and instance in node_metrics:
                    node_metrics[instance]["memory_usage_percent"] = float(result["value"][1])

            # Parse disk results
            for result in disk_results:
                instance = result["metric"].get("instance", "").split(":")[0]
                if instance and instance in node_metrics:
                    node_metrics[instance]["disk_usage_percent"] = float(result["value"][1])

            return node_metrics

        except Exception as e:
            logger.error(f"Error collecting node metrics: {e}")
            return {}

    async def _collect_pod_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Collect metrics for pods"""
        try:
            pod_metrics = {}

            # Pod CPU usage
            pod_cpu_query = 'sum(rate(container_cpu_usage_seconds_total[5m])) by (pod, namespace)'
            pod_memory_query = 'sum(container_memory_working_set_bytes) by (pod, namespace)'

            cpu_results = await self.prometheus_client.query(pod_cpu_query)
            memory_results = await self.prometheus_client.query(pod_memory_query)

            # Parse CPU results
            for result in cpu_results:
                pod_name = result["metric"].get("pod")
                namespace = result["metric"].get("namespace")
                if pod_name and namespace:
                    key = f"{namespace}/{pod_name}"
                    if key not in pod_metrics:
                        pod_metrics[key] = {"namespace": namespace, "pod": pod_name}
                    pod_metrics[key]["cpu_usage_seconds"] = float(result["value"][1])

            # Parse memory results
            for result in memory_results:
                pod_name = result["metric"].get("pod")
                namespace = result["metric"].get("namespace")
                if pod_name and namespace:
                    key = f"{namespace}/{pod_name}"
                    if key not in pod_metrics:
                        pod_metrics[key] = {"namespace": namespace, "pod": pod_name}
                    pod_metrics[key]["memory_usage_bytes"] = float(result["value"][1])

            return pod_metrics

        except Exception as e:
            logger.error(f"Error collecting pod metrics: {e}")
            return {}

    async def _detect_anomalies(self):
        """Detect anomalies in collected metrics"""
        try:
            current_time = datetime.utcnow()
            anomalies = []

            # Check cluster metrics
            cluster_metrics = self._collected_metrics.get("cluster", {}).get("metrics", {})
            if cluster_metrics.get("cpu_usage_percent", 0) > 80:
                anomalies.append({
                    "type": "high_cluster_cpu",
                    "severity": "high",
                    "metric": "cluster_cpu_usage",
                    "value": cluster_metrics["cpu_usage_percent"],
                    "threshold": 80,
                    "timestamp": current_time
                })

            if cluster_metrics.get("memory_usage_percent", 0) > 85:
                anomalies.append({
                    "type": "high_cluster_memory",
                    "severity": "high",
                    "metric": "cluster_memory_usage",
                    "value": cluster_metrics["memory_usage_percent"],
                    "threshold": 85,
                    "timestamp": current_time
                })

            # Check node metrics
            node_metrics = self._collected_metrics.get("nodes", {}).get("metrics", {})
            for node_name, metrics in node_metrics.items():
                if metrics.get("cpu_usage_percent", 0) > 90:
                    anomalies.append({
                        "type": "high_node_cpu",
                        "severity": "critical",
                        "resource": f"node/{node_name}",
                        "metric": "node_cpu_usage",
                        "value": metrics["cpu_usage_percent"],
                        "threshold": 90,
                        "timestamp": current_time
                    })

                if metrics.get("memory_usage_percent", 0) > 95:
                    anomalies.append({
                        "type": "high_node_memory",
                        "severity": "critical",
                        "resource": f"node/{node_name}",
                        "metric": "node_memory_usage",
                        "value": metrics["memory_usage_percent"],
                        "threshold": 95,
                        "timestamp": current_time
                    })

            # Update anomalies list
            self._anomalies.extend(anomalies)

            # Keep only last 100 anomalies
            if len(self._anomalies) > 100:
                self._anomalies = self._anomalies[-100:]

            # Log detected anomalies
            for anomaly in anomalies:
                logger.warning(
                    f"Anomaly detected: {anomaly['type']} - {anomaly['value']} "
                    f"(threshold: {anomaly['threshold']})"
                )

        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")

    def _clean_old_metrics(self):
        """Clean metrics older than 6 hours"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=6)
            
            for metric_type in list(self._collected_metrics.keys()):
                if self._collected_metrics[metric_type]["timestamp"] < cutoff_time:
                    del self._collected_metrics[metric_type]

        except Exception as e:
            logger.error(f"Error cleaning old metrics: {e}")

    async def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics"""
        try:
            cluster_metrics = self._collected_metrics.get("cluster", {}).get("metrics", {})
            node_metrics = self._collected_metrics.get("nodes", {}).get("metrics", {})
            pod_metrics = self._collected_metrics.get("pods", {}).get("metrics", {})

            # Calculate cluster health score
            health_score = 100
            if cluster_metrics.get("cpu_usage_percent", 0) > 80:
                health_score -= 20
            if cluster_metrics.get("memory_usage_percent", 0) > 85:
                health_score -= 20
            if cluster_metrics.get("ready_nodes", 0) < cluster_metrics.get("total_nodes", 1):
                health_score -= 30

            health_score = max(0, health_score)

            return {
                "timestamp": datetime.utcnow(),
                "cluster_health_score": health_score,
                "cluster_metrics": cluster_metrics,
                "node_count": len(node_metrics),
                "pod_count": len(pod_metrics),
                "recent_anomalies": len([a for a in self._anomalies 
                                       if a["timestamp"] > datetime.utcnow() - timedelta(minutes=30)]),
                "metrics_age_minutes": self._get_metrics_age_minutes()
            }

        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}")
            return {}

    def _get_metrics_age_minutes(self) -> float:
        """Get age of the most recent metrics in minutes"""
        try:
            if not self._collected_metrics:
                return 0
            
            latest_timestamp = max(
                data["timestamp"] 
                for data in self._collected_metrics.values() 
                if "timestamp" in data
            )
            age = datetime.utcnow() - latest_timestamp
            return age.total_seconds() / 60

        except Exception as e:
            logger.error(f"Error calculating metrics age: {e}")
            return 0

    async def get_anomalies(self, last_hours: int = 24) -> List[Dict[str, Any]]:
        """Get anomalies from the specified time range"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=last_hours)
            recent_anomalies = [
                anomaly for anomaly in self._anomalies
                if anomaly["timestamp"] >= cutoff_time
            ]
            return recent_anomalies

        except Exception as e:
            logger.error(f"Error getting anomalies: {e}")
            return []

    async def get_trends(self, metric_type: str, hours: int = 24) -> Dict[str, Any]:
        """Get trends for specific metric type"""
        # This would typically query historical data from a time series database
        # For now, return a mock response
        return {
            "metric_type": metric_type,
            "time_range_hours": hours,
            "trend": "stable",
            "average_value": 50.0,
            "max_value": 75.0,
            "min_value": 25.0
        }
