import logging
from typing import List, Dict, Any, Optional
import httpx
from datetime import datetime, timedelta
from app.config import settings

logger = logging.getLogger(__name__)


class JaegerClient:
    def __init__(self):
        self.base_url = settings.jaeger_url
        self.timeout = settings.jaeger_timeout

    async def get_services(self) -> List[str]:
        """
        Get list of traced services
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/services")
                response.raise_for_status()
                return response.json()["data"]
        except Exception as e:
            logger.error(f"Error getting Jaeger services: {e}")
            raise

    async def get_traces(self, service: str, lookback: str = "1h", 
                        limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get traces for a service
        """
        try:
            end_time = datetime.utcnow()
            start_time = end_time - self._parse_lookback(lookback)
            
            params = {
                "service": service,
                "start": int(start_time.timestamp() * 1000000),
                "end": int(end_time.timestamp() * 1000000),
                "limit": limit
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/traces", params=params)
                response.raise_for_status()
                
                data = response.json()
                return self._parse_traces_response(data)

        except Exception as e:
            logger.error(f"Error getting traces: {e}")
            raise

    async def get_trace_detail(self, trace_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific trace
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/traces/{trace_id}")
                response.raise_for_status()
                
                data = response.json()
                return self._parse_trace_detail(data)

        except Exception as e:
            logger.error(f"Error getting trace detail: {e}")
            raise

    async def analyze_latency(self, service: str, lookback: str = "1h") -> Dict[str, Any]:
        """
        Analyze latency patterns for a service
        """
        try:
            traces = await self.get_traces(service, lookback, limit=1000)
            
            if not traces:
                return {"error": "No traces found"}
            
            latencies = [trace["duration"] for trace in traces if trace["duration"]]
            errors = [trace for trace in traces if trace.get("errors", 0) > 0]
            
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                max_latency = max(latencies)
                p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
                p99_latency = sorted(latencies)[int(len(latencies) * 0.99)]
            else:
                avg_latency = max_latency = p95_latency = p99_latency = 0
            
            # Analyze slow endpoints
            slow_traces = sorted(traces, key=lambda x: x.get("duration", 0), reverse=True)[:10]
            
            return {
                "service": service,
                "total_traces": len(traces),
                "error_traces": len(errors),
                "error_rate": len(errors) / len(traces) if traces else 0,
                "latency_metrics": {
                    "average": avg_latency,
                    "max": max_latency,
                    "p95": p95_latency,
                    "p99": p99_latency
                },
                "slow_endpoints": [
                    {
                        "operation": trace.get("operationName", "unknown"),
                        "duration": trace.get("duration", 0),
                        "trace_id": trace.get("traceID")
                    }
                    for trace in slow_traces
                ],
                "common_errors": self._analyze_common_errors(errors)
            }

        except Exception as e:
            logger.error(f"Error analyzing latency: {e}")
            raise

    async def get_dependencies(self) -> Dict[str, Any]:
        """
        Get service dependencies
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/dependencies")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error getting dependencies: {e}")
            raise

    def _parse_traces_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse Jaeger traces response
        """
        traces = []
        if "data" in data:
            for trace in data["data"]:
                trace_info = {
                    "traceID": trace.get("traceID"),
                    "spans": len(trace.get("spans", [])),
                    "duration": self._calculate_trace_duration(trace),
                    "services": set(),
                    "errors": 0,
                    "operationName": trace.get("spans", [{}])[0].get("operationName", "") if trace.get("spans") else ""
                }
                
                for span in trace.get("spans", []):
                    trace_info["services"].add(span.get("process", {}).get("serviceName", "unknown"))
                    if span.get("tags"):
                        for tag in span["tags"]:
                            if tag.get("key") == "error" and tag.get("value"):
                                trace_info["errors"] += 1
                
                trace_info["services"] = list(trace_info["services"])
                traces.append(trace_info)
        
        return traces

    def _parse_trace_detail(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse detailed trace information
        """
        if "data" not in data or not data["data"]:
            return {}
        
        trace = data["data"][0]
        
        spans = []
        for span in trace.get("spans", []):
            span_info = {
                "spanID": span.get("spanID"),
                "operationName": span.get("operationName"),
                "serviceName": span.get("process", {}).get("serviceName"),
                "startTime": span.get("startTime"),
                "duration": span.get("duration"),
                "tags": span.get("tags", []),
                "references": span.get("references", [])
            }
            spans.append(span_info)
        
        return {
            "traceID": trace.get("traceID"),
            "spans": spans,
            "duration": self._calculate_trace_duration(trace),
            "service_count": len(set(span.get("process", {}).get("serviceName") for span in trace.get("spans", []))),
            "has_errors": any(
                tag.get("key") == "error" and tag.get("value")
                for span in trace.get("spans", [])
                for tag in span.get("tags", [])
            )
        }

    def _calculate_trace_duration(self, trace: Dict[str, Any]) -> float:
        """
        Calculate total trace duration in microseconds
        """
        if not trace.get("spans"):
            return 0
        
        start_times = [span.get("startTime", 0) for span in trace["spans"]]
        end_times = [span.get("startTime", 0) + span.get("duration", 0) for span in trace["spans"]]
        
        if not start_times or not end_times:
            return 0
        
        return max(end_times) - min(start_times)

    def _analyze_common_errors(self, error_traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze common error patterns
        """
        error_patterns = {}
        
        for trace in error_traces:
            # This would need actual error message extraction from span tags
            error_type = "unknown"
            error_patterns[error_type] = error_patterns.get(error_type, 0) + 1
        
        return [
            {"error_type": error_type, "count": count}
            for error_type, count in error_patterns.items()
        ]

    def _parse_lookback(self, lookback: str) -> timedelta:
        """
        Parse lookback string to timedelta
        """
        units = {
            "m": "minutes",
            "h": "hours",
            "d": "days"
        }
        
        value = int(lookback[:-1])
        unit = lookback[-1]
        
        if unit in units:
            return timedelta(**{units[unit]: value})
        else:
            return timedelta(hours=1)  # Default
