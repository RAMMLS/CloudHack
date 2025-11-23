import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.models.incident_models import Incident, ActionPlan, Severity
from app.services.kubernetes_client import KubernetesClient
from app.services.prometheus_client import PrometheusClient
from app.services.loki_client import LokiClient
from app.services.jaeger_client import JaegerClient

logger = logging.getLogger(__name__)


class IncidentAnalyzer:
    def __init__(self):
        self.k8s_client = KubernetesClient()
        self.prometheus_client = PrometheusClient()
        self.loki_client = LokiClient()
        self.jaeger_client = JaegerClient()

    async def analyze_incident(self, symptoms: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze incident symptoms and provide diagnosis
        """
        try:
            analysis = {
                "symptoms": symptoms,
                "timestamp": datetime.utcnow(),
                "analysis_steps": [],
                "findings": [],
                "root_cause": None,
                "confidence": 0.0,
                "action_plan": None
            }

            # Step 1: Check Kubernetes resources
            k8s_analysis = await self._analyze_kubernetes_state()
            analysis["analysis_steps"].append({
                "step": "kubernetes_analysis",
                "status": "completed",
                "findings": k8s_analysis.get("issues", [])
            })
            analysis["findings"].extend(k8s_analysis.get("issues", []))

            # Step 2: Check metrics and alerts
            metrics_analysis = await self._analyze_metrics()
            analysis["analysis_steps"].append({
                "step": "metrics_analysis", 
                "status": "completed",
                "findings": metrics_analysis.get("alerts", [])
            })
            analysis["findings"].extend(metrics_analysis.get("alerts", []))

            # Step 3: Check logs for errors
            logs_analysis = await self._analyze_logs()
            analysis["analysis_steps"].append({
                "step": "logs_analysis",
                "status": "completed", 
                "findings": logs_analysis.get("error_patterns", [])
            })
            analysis["findings"].extend(logs_analysis.get("error_patterns", []))

            # Step 4: Analyze traces for performance issues
            traces_analysis = await self._analyze_traces()
            analysis["analysis_steps"].append({
                "step": "traces_analysis",
                "status": "completed",
                "findings": traces_analysis.get("performance_issues", [])
            })
            analysis["findings"].extend(traces_analysis.get("performance_issues", []))

            # Determine root cause and generate action plan
            root_cause_analysis = await self._determine_root_cause(analysis["findings"])
            analysis["root_cause"] = root_cause_analysis["root_cause"]
            analysis["confidence"] = root_cause_analysis["confidence"]
            analysis["severity"] = root_cause_analysis["severity"]

            # Generate action plan
            analysis["action_plan"] = await self._generate_action_plan(
                analysis["root_cause"], 
                analysis["findings"]
            )

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing incident: {e}")
            raise

    async def _analyze_kubernetes_state(self) -> Dict[str, Any]:
        """
        Analyze Kubernetes cluster state
        """
        try:
            issues = []
            
            # Check nodes
            nodes = await self.k8s_client.get_nodes()
            for node in nodes:
                if node["status"] != "Ready":
                    issues.append({
                        "type": "node_not_ready",
                        "severity": Severity.CRITICAL,
                        "resource": f"node/{node['name']}",
                        "description": f"Node {node['name']} is not ready",
                        "suggested_actions": [
                            "Check node resources and kubelet status",
                            "Verify network connectivity",
                            "Review node events for details"
                        ]
                    })

            # Check pods
            pods = await self.k8s_client.get_pods()
            for pod in pods:
                if pod["status"] == "CrashLoopBackOff":
                    issues.append({
                        "type": "pod_crash_loop",
                        "severity": Severity.HIGH,
                        "resource": f"pod/{pod['namespace']}/{pod['name']}",
                        "description": f"Pod {pod['name']} in CrashLoopBackOff",
                        "suggested_actions": [
                            "Check pod logs for application errors",
                            "Verify resource limits and requests",
                            "Review container configuration"
                        ]
                    })
                elif pod["restarts"] > 10:
                    issues.append({
                        "type": "frequent_restarts",
                        "severity": Severity.MEDIUM,
                        "resource": f"pod/{pod['namespace']}/{pod['name']}",
                        "description": f"Pod {pod['name']} has restarted {pod['restarts']} times",
                        "suggested_actions": [
                            "Investigate application stability",
                            "Check for memory leaks",
                            "Review liveness/readiness probes"
                        ]
                    })

            # Check events for warnings
            events = await self.k8s_client.get_events()
            warning_events = [e for e in events if e["type"] == "Warning"]
            for event in warning_events[:10]:  # Limit to first 10 warnings
                issues.append({
                    "type": "kubernetes_warning",
                    "severity": Severity.MEDIUM,
                    "resource": f"{event['involved_object']['kind']}/{event['namespace']}/{event['involved_object']['name']}",
                    "description": f"{event['reason']}: {event['message']}",
                    "suggested_actions": [
                        "Review event details for specific causes",
                        "Check related resource configurations"
                    ]
                })

            return {"issues": issues}

        except Exception as e:
            logger.error(f"Error analyzing Kubernetes state: {e}")
            return {"issues": []}

    async def _analyze_metrics(self) -> Dict[str, Any]:
        """
        Analyze Prometheus metrics and alerts
        """
        try:
            alerts = []
            
            # Check firing alerts
            try:
                firing_alerts = await self.prometheus_client.check_alerts()
                for alert in firing_alerts:
                    alerts.append({
                        "type": "prometheus_alert",
                        "severity": self._map_alert_severity(alert.get("severity", "warning")),
                        "resource": alert.get("instance", "unknown"),
                        "description": f"Alert {alert['name']} is firing",
                        "suggested_actions": [
                            "Review alert rules and thresholds",
                            "Check related metrics for root cause",
                            "Verify resource utilization"
                        ]
                    })
            except Exception as e:
                logger.warning(f"Could not fetch alerts: {e}")

            # Check cluster metrics for anomalies
            try:
                cluster_metrics = await self.prometheus_client.get_cluster_metrics()
                
                # Analyze node metrics
                for metric_type, metric_data in cluster_metrics.get("node_metrics", {}).items():
                    for metric in metric_data:
                        value = float(metric["value"][1]) if metric.get("value") else 0
                        if value > 80:  # High utilization threshold
                            alerts.append({
                                "type": f"high_{metric_type}",
                                "severity": Severity.HIGH,
                                "resource": metric["metric"].get("instance", "unknown"),
                                "description": f"High {metric_type}: {value:.1f}%",
                                "suggested_actions": [
                                    "Consider scaling resources",
                                    "Check for resource leaks",
                                    "Review resource requests/limits"
                                ]
                            })
            except Exception as e:
                logger.warning(f"Could not analyze cluster metrics: {e}")

            return {"alerts": alerts}

        except Exception as e:
            logger.error(f"Error analyzing metrics: {e}")
            return {"alerts": []}

    async def _analyze_logs(self) -> Dict[str, Any]:
        """
        Analyze application logs for errors
        """
        try:
            error_patterns = []
            
            # Search for recent errors
            errors = await self.loki_client.search_errors(time_range="1h")
            
            if errors:
                # Group errors by service
                errors_by_service = {}
                for error in errors:
                    service = error["labels"].get("job", "unknown")
                    if service not in errors_by_service:
                        errors_by_service[service] = []
                    errors_by_service[service].append(error)
                
                for service, service_errors in errors_by_service.items():
                    error_count = len(service_errors)
                    error_patterns.append({
                        "type": "application_errors",
                        "severity": Severity.HIGH if error_count > 10 else Severity.MEDIUM,
                        "resource": f"service/{service}",
                        "description": f"Found {error_count} errors in {service}",
                        "sample_messages": [e["message"] for e in service_errors[:3]],
                        "suggested_actions": [
                            "Review application logs for root cause",
                            "Check recent deployments or changes",
                            "Verify dependencies and connections"
                        ]
                    })

            return {"error_patterns": error_patterns}

        except Exception as e:
            logger.error(f"Error analyzing logs: {e}")
            return {"error_patterns": []}

    async def _analyze_traces(self) -> Dict[str, Any]:
        """
        Analyze distributed traces for performance issues
        """
        try:
            performance_issues = []
            
            services = await self.jaeger_client.get_services()
            
            for service in services[:5]:  # Analyze first 5 services
                try:
                    latency_analysis = await self.jaeger_client.analyze_latency(service, lookback="1h")
                    
                    if latency_analysis.get("error_rate", 0) > 0.1:  # 10% error rate
                        performance_issues.append({
                            "type": "high_error_rate",
                            "severity": Severity.HIGH,
                            "resource": f"service/{service}",
                            "description": f"High error rate: {latency_analysis['error_rate']:.1%}",
                            "suggested_actions": [
                                "Investigate failing requests",
                                "Check service dependencies",
                                "Review recent changes"
                            ]
                        })
                    
                    if latency_analysis["latency_metrics"]["p95"] > 1000000:  # 1 second
                        performance_issues.append({
                            "type": "high_latency",
                            "severity": Severity.MEDIUM,
                            "resource": f"service/{service}",
                            "description": f"High p95 latency: {latency_analysis['latency_metrics']['p95']:.0f}μs",
                            "suggested_actions": [
                                "Optimize database queries",
                                "Review external API calls",
                                "Check resource utilization"
                            ]
                        })
                        
                except Exception as e:
                    logger.warning(f"Could not analyze traces for {service}: {e}")
                    continue

            return {"performance_issues": performance_issues}

        except Exception as e:
            logger.error(f"Error analyzing traces: {e}")
            return {"performance_issues": []}

    async def _determine_root_cause(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Determine the most likely root cause from findings
        """
        if not findings:
            return {
                "root_cause": "No issues detected",
                "confidence": 1.0,
                "severity": Severity.INFO
            }

        # Group findings by severity and type
        critical_findings = [f for f in findings if f.get("severity") == Severity.CRITICAL]
        high_findings = [f for f in findings if f.get("severity") == Severity.HIGH]
        
        if critical_findings:
            return {
                "root_cause": critical_findings[0]["description"],
                "confidence": 0.9,
                "severity": Severity.CRITICAL
            }
        elif high_findings:
            return {
                "root_cause": high_findings[0]["description"],
                "confidence": 0.7,
                "severity": Severity.HIGH
            }
        else:
            return {
                "root_cause": findings[0]["description"],
                "confidence": 0.5,
                "severity": Severity.MEDIUM
            }

    async def _generate_action_plan(self, root_cause: str, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate action plan based on root cause and findings
        """
        steps = []
        
        # Immediate actions
        steps.append({
            "step": 1,
            "action": "Acknowledge the incident and assess impact",
            "estimated_duration": 5,
            "critical": True
        })
        
        steps.append({
            "step": 2, 
            "action": "Gather additional context and metrics",
            "estimated_duration": 10,
            "critical": True
        })
        
        # Specific actions based on findings
        for i, finding in enumerate(findings[:3]):  # Limit to first 3 findings
            if finding.get("suggested_actions"):
                for j, action in enumerate(finding["suggested_actions"][:2]):  # First 2 actions per finding
                    steps.append({
                        "step": len(steps) + 1,
                        "action": action,
                        "estimated_duration": 15,
                        "critical": False,
                        "related_finding": finding["type"]
                    })
        
        # Verification step
        steps.append({
            "step": len(steps) + 1,
            "action": "Verify resolution and monitor system stability",
            "estimated_duration": 10,
            "critical": True
        })
        
        return {
            "root_cause": root_cause,
            "total_steps": len(steps),
            "estimated_total_duration": sum(step["estimated_duration"] for step in steps),
            "critical_steps": [step for step in steps if step.get("critical", False)],
            "steps": steps
        }

    def _map_alert_severity(self, prometheus_severity: str) -> Severity:
        """
        Map Prometheus alert severity to internal severity
        """
        mapping = {
            "critical": Severity.CRITICAL,
            "warning": Severity.MEDIUM,
            "info": Severity.LOW
        }
        return mapping.get(prometheus_severity.lower(), Severity.MEDIUM)
