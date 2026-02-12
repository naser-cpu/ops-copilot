"""API routes for the lab assistant."""

import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from redis import Redis
from rq import Queue
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Request
from api.schemas import (
    AgentResult,
    HealthResponse,
    LabRequestCreate,
    LabRequestResponse,
    LabRequestStatus,
    RequestStatus,
)

router = APIRouter()

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


def get_redis() -> Redis:
    """Get Redis connection."""
    return Redis.from_url(REDIS_URL)


def get_queue() -> Queue:
    """Get RQ queue."""
    return Queue("lab_requests", connection=get_redis())


@router.post("/requests", response_model=LabRequestResponse, status_code=201)
def create_request(
    request_data: LabRequestCreate,
    db: Session = Depends(get_db),
) -> LabRequestResponse:
    """
    Submit a new lab request for async processing.

    The request will be queued and processed by the agent worker.
    """
    # Create database record
    db_request = Request(
        text=request_data.text,
        priority=request_data.priority.value,
        status=RequestStatus.QUEUED.value,
    )
    db.add(db_request)
    db.commit()
    db.refresh(db_request)

    # Enqueue the task
    queue = get_queue()
    queue.enqueue(
        "worker.tasks.process_request",
        db_request.id,
        job_id=db_request.id,
        job_timeout="5m",
        at_front=(request_data.priority == "high"),
    )

    return LabRequestResponse(
        request_id=db_request.id,
        status=RequestStatus.QUEUED,
    )


@router.get("/requests/{request_id}", response_model=LabRequestStatus)
def get_request_status(
    request_id: str,
    db: Session = Depends(get_db),
) -> LabRequestStatus:
    """
    Get the status and result of a lab request.

    Returns the current status and, if complete, the agent's result.
    """
    db_request = db.query(Request).filter(Request.id == request_id).first()

    if not db_request:
        raise HTTPException(status_code=404, detail="Request not found")

    # Parse result if present
    result = None
    if db_request.result:
        result = AgentResult(**db_request.result)

    return LabRequestStatus(
        request_id=db_request.id,
        status=RequestStatus(db_request.status),
        result=result,
        error=db_request.error,
    )


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """
    Health check endpoint.

    Returns the status of the API and its dependent services.
    """
    services = {}

    # Check database
    try:
        db.execute(text("SELECT 1"))
        services["database"] = "healthy"
    except Exception as e:
        services["database"] = f"unhealthy: {str(e)}"

    # Check Redis
    try:
        redis = get_redis()
        redis.ping()
        services["redis"] = "healthy"
    except Exception as e:
        services["redis"] = f"unhealthy: {str(e)}"

    # Check queue
    try:
        queue = get_queue()
        services["queue"] = f"healthy ({len(queue)} jobs pending)"
    except Exception as e:
        services["queue"] = f"unhealthy: {str(e)}"

    overall_status = "healthy" if all("healthy" in v for v in services.values()) else "degraded"

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        services=services,
    )
