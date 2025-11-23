import os
from typing import Optional
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    # Server Configuration
    server_host: str = Field(default="0.0.0.0", env="SERVER_HOST")
    server_port: int = Field(default=8000, env="SERVER_PORT")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Kubernetes Configuration
    kubeconfig_path: str = Field(default="/app/.kube/config", env="KUBECONFIG_PATH")
    k8s_context: str = Field(default="default", env="K8S_CONTEXT")
    k8s_namespace: str = Field(default="default", env="K8S_NAMESPACE")
    
    # External Services
    prometheus_url: str = Field(default="http://prometheus:9090", env="PROMETHEUS_URL")
    prometheus_timeout: int = Field(default=30, env="PROMETHEUS_TIMEOUT")
    
    loki_url: str = Field(default="http://loki:3100", env="LOKI_URL")
    loki_timeout: int = Field(default=30, env="LOKI_TIMEOUT")
    
    jaeger_url: str = Field(default="http://jaeger:16686", env="JAEGER_URL")
    jaeger_timeout: int = Field(default=30, env="JAEGER_TIMEOUT")
    
    # Database
    database_url: str = Field(default="postgresql://sre_user:sre_password@postgres:5432/sre_agent", env="DATABASE_URL")
    
    # Redis
    redis_url: str = Field(default="redis://redis:6379/0", env="REDIS_URL")
    
    # Security
    secret_key: str = Field(default="your-secret-key-here", env="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Monitoring
    metrics_port: int = Field(default=8001, env="METRICS_PORT")
    health_check_timeout: int = Field(default=30, env="HEALTH_CHECK_TIMEOUT")
    
    # Cloud Provider
    cloud_provider: str = Field(default="aws", env="CLOUD_PROVIDER")
    aws_region: str = Field(default="us-east-1", env="AWS_REGION")
    gcp_project: str = Field(default="your-project", env="GCP_PROJECT")
    azure_subscription: str = Field(default="your-subscription", env="AZURE_SUBSCRIPTION")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
