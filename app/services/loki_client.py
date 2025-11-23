import logging
from typing import List, Dict, Any, Optional
import httpx
from datetime import datetime, timedelta
from app.config import settings

logger = logging.getLogger(__name__)


class LokiClient:
    def __init__(self):
        self.base_url = settings.loki_url
        self.timeout = settings.loki_timeout

    async def query_logs(self, query: str, limit: int = 100, start_time: Optional[datetime] = None, 
                        end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Query logs from Loki
        """
        try:
            if not start_time:
                start_time = datetime.utcnow() - timedelta(hours=1)
            if not end_time:
                end_time = datetime.utcnow()

            params = {
                "query": query,
                "limit": limit,
                "start": start_time.isoformat() + "Z",
                "end": end_time.isoformat() + "Z",
                "direction": "backward"
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/loki/api/v1/query_range", params=params)
                response.raise_for_status()
                
                data = response.json()
                return self._parse_loki_response(data)

        except Exception as e:
            logger.error(f"Error querying Loki: {e}")
            raise

    async def get_pod_logs(self, pod_name: str, namespace: str = "default", 
                          container: str = None, tail_lines: int = 100) -> List[Dict[str, Any]]:
        """
        Get logs for a specific pod
        """
        try:
            query = f'{{pod="{pod_name}", namespace="{namespace}"}}'
            if container:
                query = f'{{pod="{pod_name}", namespace="{namespace}", container="{container}"}}'

            logs = await self.query_logs(query, limit=tail_lines)
            return logs

        except Exception as e:
            logger.error(f"Error getting pod logs: {e}")
            raise

    async def search_errors(self, namespace: str = None, time_range: str = "1h") -> List[Dict[str, Any]]:
        """
        Search for error logs
        """
        try:
            base_query = '{job=~".+"} |~ "(?i)error|exception|fail|critical|panic"'
            if namespace:
                base_query = f'{{namespace="{namespace}"}} |~ "(?i)error|exception|fail|critical|panic"'

            end_time = datetime.utcnow()
            start_time = end_time - self._parse_time_range(time_range)

            errors = await self.query_logs(base_query, limit=500, start_time=start_time, end_time=end_time)
            return errors

        except Exception as e:
            logger.error(f"Error searching error logs: {e}")
            raise

    async def get_log_patterns(self, namespace: str = None, time_range: str = "24h") -> Dict[str, Any]:
        """
        Analyze log patterns and frequencies
        """
        try:
            base_query = '{job=~".+"}'
            if namespace:
                base_query = f'{{namespace="{namespace}"}}'

            end_time = datetime.utcnow()
            start_time = end_time - self._parse_time_range(time_range)

            # Get log volume over time
            volume_query = f'rate({base_query}[1m])'
            
            # Get top error messages
            error_query = f'{base_query} |~ "(?i)error" | line_format "{{.msg}}"'

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Get log volume
                volume_params = {
                    "query": volume_query,
                    "start": start_time.isoformat() + "Z",
                    "end": end_time.isoformat() + "Z",
                    "step": "300"  # 5 minutes
                }
                volume_response = await client.get(f"{self.base_url}/loki/api/v1/query_range", params=volume_params)
                volume_response.raise_for_status()

                # Get error patterns
                error_params = {
                    "query": error_query,
                    "limit": 100,
                    "start": start_time.isoformat() + "Z",
                    "end": end_time.isoformat() + "Z"
                }
                error_response = await client.get(f"{self.base_url}/loki/api/v1/query_range", params=error_params)
                error_response.raise_for_status()

            volume_data = volume_response.json()
            error_data = error_response.json()

            return {
                "log_volume": self._parse_loki_response(volume_data),
                "error_patterns": self._analyze_error_patterns(error_data),
                "time_range": {
                    "start": start_time,
                    "end": end_time
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing log patterns: {e}")
            raise

    def _parse_loki_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse Loki API response
        """
        logs = []
        if "data" in data and "result" in data["data"]:
            for result in data["data"]["result"]:
                stream = result.get("stream", {})
                values = result.get("values", [])
                
                for timestamp, message in values:
                    log_entry = {
                        "timestamp": datetime.fromtimestamp(int(timestamp) / 1e9),
                        "message": message,
                        "stream": stream,
                        "labels": stream
                    }
                    logs.append(log_entry)
        
        return logs

    def _analyze_error_patterns(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze error patterns from log data
        """
        logs = self._parse_loki_response(data)
        
        error_counts = {}
        services_with_errors = set()
        
        for log in logs:
            message = log["message"]
            service = log["labels"].get("job", "unknown")
            services_with_errors.add(service)
            
            # Simple pattern analysis
            if "timeout" in message.lower():
                error_counts["timeout"] = error_counts.get("timeout", 0) + 1
            elif "connection refused" in message.lower():
                error_counts["connection_refused"] = error_counts.get("connection_refused", 0) + 1
            elif "out of memory" in message.lower():
                error_counts["out_of_memory"] = error_counts.get("out_of_memory", 0) + 1
            elif "permission denied" in message.lower():
                error_counts["permission_denied"] = error_counts.get("permission_denied", 0) + 1
            else:
                error_counts["other"] = error_counts.get("other", 0) + 1
        
        return {
            "total_errors": len(logs),
            "error_types": error_counts,
            "affected_services": list(services_with_errors),
            "sample_errors": logs[:10]  # First 10 errors as samples
        }

    def _parse_time_range(self, time_range: str) -> timedelta:
        """
        Parse time range string to timedelta
        """
        units = {
            "m": "minutes",
            "h": "hours", 
            "d": "days",
            "w": "weeks"
        }
        
        value = int(time_range[:-1])
        unit = time_range[-1]
        
        if unit in units:
            return timedelta(**{units[unit]: value})
        else:
            return timedelta(hours=1)  # Default
