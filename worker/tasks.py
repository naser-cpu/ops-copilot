"""RQ task definitions for processing lab requests."""

import logging
import traceback
from datetime import datetime

from api.database import get_db_session
from api.models import Request
from api.schemas import RequestStatus
from worker.agent.executor import execute_plan
from worker.agent.planner import create_plan

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_request(request_id: str) -> dict:
    """
    Process a lab request through the agent workflow.

    Steps:
    1. Update status to 'running'
    2. Run planner to create execution plan
    3. Run executor to execute plan and gather results
    4. Store final result and update status to 'done'

    Args:
        request_id: UUID of the request to process

    Returns:
        The final result dictionary
    """
    logger.info(f"Processing request {request_id}")

    with get_db_session() as db:
        # Fetch the request
        db_request = db.query(Request).filter(Request.id == request_id).first()
        if not db_request:
            logger.error(f"Request {request_id} not found")
            raise ValueError(f"Request {request_id} not found")

        try:
            # Update status to running
            db_request.status = RequestStatus.RUNNING.value
            db_request.started_at = datetime.utcnow()
            db.commit()

            # Step A: Create plan
            logger.info(f"Creating plan for request {request_id}")
            plan = create_plan(db_request.text)
            db_request.plan = plan.model_dump(mode="json")
            db.commit()

            # Step B: Execute plan
            logger.info(f"Executing plan for request {request_id}")
            result, tool_calls = execute_plan(db_request.text, plan, db)

            # Store results
            db_request.result = result.model_dump(mode="json")
            db_request.tool_calls = [tc.model_dump(mode="json") for tc in tool_calls]
            db_request.status = RequestStatus.DONE.value
            db_request.completed_at = datetime.utcnow()
            db.commit()

            logger.info(f"Successfully processed request {request_id}")
            return result.model_dump()

        except Exception as e:
            logger.error(f"Error processing request {request_id}: {e}")
            logger.error(traceback.format_exc())

            # Update status to failed
            db.rollback()
            db_request.status = RequestStatus.FAILED.value
            db_request.error = str(e)
            db_request.completed_at = datetime.utcnow()
            db.commit()

            raise
