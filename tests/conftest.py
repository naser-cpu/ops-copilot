"""Pytest configuration and fixtures."""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test environment
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://labassistant:labassistant@localhost:5432/labassistant",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("USE_REAL_LLM", "false")


@pytest.fixture(scope="session")
def db_engine():
    """Create database engine for tests."""
    database_url = os.getenv("DATABASE_URL")
    engine = create_engine(database_url)
    return engine


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a new database session for a test."""
    connection = db_engine.connect()
    transaction = connection.begin()

    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="session")
def test_client():
    """Create FastAPI test client."""
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_request_data():
    """Sample request data for testing."""
    return {
        "text": "How do I handle a database connection timeout?",
        "priority": "high",
    }


@pytest.fixture
def sample_plan():
    """Sample plan for testing."""
    from api.schemas import AgentPlan, PlanStep

    return AgentPlan(
        reasoning="Test reasoning",
        steps=[
            PlanStep(
                step_number=1,
                action="Search documentation",
                tool="search_docs",
                tool_input="database timeout",
            ),
            PlanStep(
                step_number=2,
                action="Query incidents",
                tool="query_incidents",
                tool_input="database",
            ),
            PlanStep(
                step_number=3,
                action="Synthesize",
                tool=None,
                tool_input=None,
            ),
        ],
    )
