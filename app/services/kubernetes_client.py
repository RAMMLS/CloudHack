import logging
from typing import List, Dict, Any, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from app.config import settings

logger = logging.getLogger(__name__)


class KubernetesClient:
    def __init__(self):
        self._client = None
        self._apps_v1 = None
        self._networking_v1 = None
        self._core_v1 = None
        self._initialize_client()

    def _initialize_client(self):
        try:
            if settings.kubeconfig_path:
                config.load_kube_config(config_file=settings.kubeconfig_path)
            else:
                config.load_incluster_config()
            
            self._client = client
            self._core_v1 = client.CoreV1Api()
            self._apps_v1 = client.AppsV1Api()
            self._networking_v1 = client.NetworkingV1Api()
            self._batch_v1 = client.BatchV1Api()
            
            logger.info("Kubernetes client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")
            raise

    async def get_cluster_info(self) -> Dict[str, Any]:
        try:
            version = self._client.VersionApi().get_code()
            nodes = self._core_v1.list_node()
            
            return {
                "kubernetes_version": version.git_version,
                "platform": version.platform,
                "total_nodes": len(nodes.items),
                "cluster_name": "default"  # Можно получить из конфигурации
            }
        except ApiException as e:
            logger.error(f"Error getting cluster info: {e}")
            raise

    async def get_nodes(self) -> List[Dict[str, Any]]:
        try:
            nodes = self._core_v1.list_node()
            node_list = []
            
            for node in nodes.items:
                conditions = {condition.type: condition.status for condition in node.status.conditions}
                
                node_info = {
                    "name": node.metadata.name,
                    "status": "Ready" if conditions.get("Ready") == "True" else "NotReady",
                    "roles": [label.split("/")[-1] for label in node.metadata.labels.keys() 
                             if label.startswith("node-role.kubernetes.io/")],
                    "age": str(node.metadata.creation_timestamp),
                    "version": node.status.node_info.kubelet_version,
                    "internal_ip": next((addr.address for addr in node.status.addresses 
                                       if addr.type == "InternalIP"), None),
                    "external_ip": next((addr.address for addr in node.status.addresses 
                                       if addr.type == "ExternalIP"), None),
                    "conditions": conditions,
                    "capacity": node.status.capacity,
                    "allocatable": node.status.allocatable
                }
                node_list.append(node_info)
            
            return node_list
        except ApiException as e:
            logger.error(f"Error getting nodes: {e}")
            raise

    async def get_pods(self, namespace: str = None) -> List[Dict[str, Any]]:
        try:
            if namespace:
                pods = self._core_v1.list_namespaced_pod(namespace)
            else:
                pods = self._core_v1.list_pod_for_all_namespaces()
            
            pod_list = []
            
            for pod in pods.items:
                container_statuses = []
                for container in pod.status.container_statuses or []:
                    container_statuses.append({
                        "name": container.name,
                        "ready": container.ready,
                        "restart_count": container.restart_count,
                        "state": container.state.to_dict() if container.state else None
                    })
                
                pod_info = {
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "status": pod.status.phase,
                    "ready": f"{sum(1 for cs in pod.status.container_statuses or [] if cs.ready)}/{len(pod.status.container_statuses or [])}",
                    "restarts": sum(cs.restart_count for cs in pod.status.container_statuses or []),
                    "age": str(pod.metadata.creation_timestamp),
                    "node": pod.spec.node_name,
                    "ip": pod.status.pod_ip,
                    "labels": pod.metadata.labels,
                    "container_statuses": container_statuses
                }
                pod_list.append(pod_info)
            
            return pod_list
        except ApiException as e:
            logger.error(f"Error getting pods: {e}")
            raise

    async def get_deployments(self, namespace: str = None) -> List[Dict[str, Any]]:
        try:
            if namespace:
                deployments = self._apps_v1.list_namespaced_deployment(namespace)
            else:
                deployments = self._apps_v1.list_deployment_for_all_namespaces()
            
            deployment_list = []
            
            for deployment in deployments.items:
                deployment_info = {
                    "name": deployment.metadata.name,
                    "namespace": deployment.metadata.namespace,
                    "ready": f"{deployment.status.ready_replicas or 0}/{deployment.status.replicas or 0}",
                    "up_to_date": deployment.status.updated_replicas or 0,
                    "available": deployment.status.available_replicas or 0,
                    "age": str(deployment.metadata.creation_timestamp),
                    "strategy": deployment.spec.strategy.type if deployment.spec.strategy else "RollingUpdate"
                }
                deployment_list.append(deployment_info)
            
            return deployment_list
        except ApiException as e:
            logger.error(f"Error getting deployments: {e}")
            raise

    async def get_services(self, namespace: str = None) -> List[Dict[str, Any]]:
        try:
            if namespace:
                services = self._core_v1.list_namespaced_service(namespace)
            else:
                services = self._core_v1.list_service_for_all_namespaces()
            
            service_list = []
            
            for service in services.items:
                ports = []
                for port in service.spec.ports or []:
                    ports.append(f"{port.port}/{port.protocol}")
                
                service_info = {
                    "name": service.metadata.name,
                    "namespace": service.metadata.namespace,
                    "type": service.spec.type,
                    "cluster_ip": service.spec.cluster_ip,
                    "external_ip": service.spec.external_ips[0] if service.spec.external_ips else None,
                    "ports": ports,
                    "age": str(service.metadata.creation_timestamp),
                    "selector": service.spec.selector or {}
                }
                service_list.append(service_info)
            
            return service_list
        except ApiException as e:
            logger.error(f"Error getting services: {e}")
            raise

    async def get_events(self, namespace: str = None) -> List[Dict[str, Any]]:
        try:
            if namespace:
                events = self._core_v1.list_namespaced_event(namespace)
            else:
                events = self._core_v1.list_event_for_all_namespaces()
            
            event_list = []
            
            for event in events.items:
                event_info = {
                    "name": event.metadata.name,
                    "namespace": event.metadata.namespace,
                    "type": event.type,
                    "reason": event.reason,
                    "message": event.message,
                    "count": event.count,
                    "first_seen": str(event.first_timestamp or event.metadata.creation_timestamp),
                    "last_seen": str(event.last_timestamp or event.metadata.creation_timestamp),
                    "involved_object": {
                        "kind": event.involved_object.kind,
                        "name": event.involved_object.name,
                        "namespace": event.involved_object.namespace
                    }
                }
                event_list.append(event_info)
            
            return event_list
        except ApiException as e:
            logger.error(f"Error getting events: {e}")
            raise

    async def get_namespaces(self) -> List[Dict[str, Any]]:
        try:
            namespaces = self._core_v1.list_namespace()
            namespace_list = []
            
            for namespace in namespaces.items:
                namespace_info = {
                    "name": namespace.metadata.name,
                    "status": namespace.status.phase,
                    "age": str(namespace.metadata.creation_timestamp),
                    "labels": namespace.metadata.labels
                }
                namespace_list.append(namespace_info)
            
            return namespace_list
        except ApiException as e:
            logger.error(f"Error getting namespaces: {e}")
            raise
