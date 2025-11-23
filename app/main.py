import logging
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from app.config import settings
from app.api import routers
from app.core.database import init_db, close_db
from app.core.middleware import LoggingMiddleware, ErrorHandlingMiddleware
from app.services.health_check import HealthCheckService
from app.services.metrics_collector import MetricsCollector

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting SRE Agent Backend")
    await init_db()
    
    # Initialize metrics collector
    metrics_collector = MetricsCollector()
    await metrics_collector.start()
    
    yield
    
    # Shutdown
    logger.info("Shutting down SRE Agent Backend")
    await close_db()
    await metrics_collector.stop()


app = FastAPI(
    title="SRE Agent for Kubernetes",
    description="Интеллектуальный помощник для диагностики и управления Kubernetes кластерами",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)
app.add_middleware(ErrorHandlingMiddleware)

# Include routers
app.include_router(routers.kubernetes_router, prefix="/api/v1", tags=["kubernetes"])
app.include_router(routers.metrics_router, prefix="/api/v1", tags=["metrics"])
app.include_router(routers.logs_router, prefix="/api/v1", tags=["logs"])
app.include_router(routers.traces_router, prefix="/api/v1", tags=["traces"])
app.include_router(routers.analysis_router, prefix="/api/v1", tags=["analysis"])
app.include_router(routers.health_router, prefix="/api/v1", tags=["health"])
app.include_router(routers.incidents_router, prefix="/api/v1", tags=["incidents"])


@app.get("/")
async def root():
    return {
        "message": "SRE Agent for Kubernetes API",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    health_service = HealthCheckService()
    health_status = await health_service.check_all_services()
    
    if health_status["overall_status"] == "healthy":
        return health_status
    else:
        raise HTTPException(status_code=503, detail=health_status)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
