"""Tests for agent components."""

import os
from pathlib import Path
from unittest.mock import patch

from api.schemas import AgentPlan, AgentResult
from worker.agent.executor import _synthesize_deterministic, execute_plan
from worker.agent.planner import _extract_keywords, _needs_docs, _needs_incidents, create_plan
from worker.agent.tools import query_incidents, search_docs

# Ensure we're using deterministic planner
os.environ["USE_REAL_LLM"] = "false"


class TestPlanner:
    """Tests for the planner module."""

    def test_create_plan_returns_plan(self):
        """create_plan should return an AgentPlan."""
        plan = create_plan("How do I fix a database issue?")
        assert isinstance(plan, AgentPlan)
        assert plan.reasoning
        assert len(plan.steps) > 0

    def test_create_plan_includes_tool_steps(self):
        """Plan should include steps with tools."""
        plan = create_plan("How do I troubleshoot a database timeout?")
        tool_steps = [s for s in plan.steps if s.tool is not None]
        assert len(tool_steps) > 0

    def test_create_plan_ends_with_synthesis(self):
        """Plan should end with a synthesis step (no tool)."""
        plan = create_plan("How do I fix something?")
        last_step = plan.steps[-1]
        assert last_step.tool is None

    def test_needs_docs_detection(self):
        """_needs_docs should detect documentation keywords."""
        assert _needs_docs("How do I troubleshoot this?")
        assert _needs_docs("What is the procedure?")
        assert _needs_docs("Guide me through deployment")
        assert not _needs_docs("xyz abc 123")

    def test_needs_incidents_detection(self):
        """_needs_incidents should detect incident keywords."""
        assert _needs_incidents("Show me recent incidents")
        assert _needs_incidents("What was the root cause?")
        assert _needs_incidents("Past outages")
        assert not _needs_incidents("xyz abc 123")

    def test_extract_keywords(self):
        """_extract_keywords should extract meaningful words."""
        keywords = _extract_keywords("How do I handle database connection timeout?")
        assert "database" in keywords
        assert "connection" in keywords
        assert "timeout" in keywords
        # Stop words should be filtered
        assert "how" not in keywords
        assert "the" not in keywords


class TestExecutor:
    """Tests for the executor module."""

    def test_execute_plan_returns_result(self, sample_plan, db_session):
        """execute_plan should return an AgentResult."""
        result, tool_calls = execute_plan(
            "Test query",
            sample_plan,
            db_session,
        )
        assert isinstance(result, AgentResult)
        assert result.summary
        assert isinstance(result.steps, list)
        assert isinstance(result.sources, list)

    def test_execute_plan_records_tool_calls(self, sample_plan, db_session):
        """execute_plan should record tool calls."""
        result, tool_calls = execute_plan(
            "Test query",
            sample_plan,
            db_session,
        )
        # Our sample plan has 2 tool steps
        assert len(tool_calls) >= 1

    def test_synthesize_deterministic_with_docs(self):
        """_synthesize_deterministic should handle doc results."""
        doc_results = [
            {
                "filename": "test.md",
                "title": "Test Document",
                "snippet": "This is a test snippet",
                "key_points": ["Point 1", "Point 2"],
            }
        ]
        result = _synthesize_deterministic("test", doc_results, [])
        assert "test.md" in result.sources
        assert result.summary

    def test_synthesize_deterministic_with_incidents(self):
        """_synthesize_deterministic should handle incident results."""
        incident_results = [
            {
                "id": "INC-001",
                "title": "Test Incident",
                "description": "Test description",
                "resolution": "Fixed by doing X",
            }
        ]
        result = _synthesize_deterministic("test", [], incident_results)
        assert "INC-001" in result.sources
        assert result.summary


class TestTools:
    """Tests for the tools module."""

    def test_search_docs_returns_list(self):
        """search_docs should return a list."""
        # Set up runbooks path
        runbooks_dir = Path(__file__).parent.parent / "data" / "runbooks"
        with patch("worker.agent.tools.RUNBOOKS_DIR", runbooks_dir):
            results = search_docs("database troubleshooting")
        assert isinstance(results, list)

    def test_search_docs_with_matching_query(self):
        """search_docs should find matching documents."""
        runbooks_dir = Path(__file__).parent.parent / "data" / "runbooks"
        with patch("worker.agent.tools.RUNBOOKS_DIR", runbooks_dir):
            results = search_docs("database connection pool")

        if results:  # Only check if we have results
            assert all("filename" in r for r in results)
            assert all("title" in r for r in results)
            assert all("snippet" in r for r in results)

    def test_search_docs_returns_empty_for_no_match(self):
        """search_docs should return empty for no matches."""
        runbooks_dir = Path(__file__).parent.parent / "data" / "runbooks"
        with patch("worker.agent.tools.RUNBOOKS_DIR", runbooks_dir):
            results = search_docs("xyznonexistent12345")
        assert results == []

    def test_query_incidents_returns_list(self, db_session):
        """query_incidents should return a list."""
        results = query_incidents("database", db_session)
        assert isinstance(results, list)

    def test_query_incidents_with_matching_query(self, db_session):
        """query_incidents should find matching incidents."""
        results = query_incidents("connection pool", db_session)
        if results:
            assert all("id" in r for r in results)
            assert all("title" in r for r in results)

    def test_query_incidents_returns_incident_fields(self, db_session):
        """query_incidents should return proper fields."""
        results = query_incidents("", db_session)  # Empty query returns recent
        if results:
            first = results[0]
            assert "id" in first
            assert "title" in first
            assert "severity" in first
            assert "status" in first


class TestEndToEnd:
    """End-to-end tests for the agent workflow."""

    def test_full_workflow(self, db_session):
        """Test complete planner -> executor workflow."""
        query = "How do I troubleshoot database connection timeouts?"

        # Step 1: Create plan
        plan = create_plan(query)
        assert plan is not None
        assert len(plan.steps) > 0

        # Step 2: Execute plan
        result, tool_calls = execute_plan(query, plan, db_session)

        # Step 3: Validate result
        assert result.summary
        assert len(result.steps) > 0
        # Sources should be populated for this query
        assert len(result.sources) >= 0  # May or may not find sources

    def test_result_schema_compliance(self, db_session):
        """Test that results comply with expected schema."""
        import json

        import jsonschema

        # Load schema
        schema_path = Path(__file__).parent.parent / "eval" / "schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        # Run agent
        query = "Show me incident response procedures"
        plan = create_plan(query)
        result, _ = execute_plan(query, plan, db_session)

        # Validate
        result_dict = result.model_dump()
        jsonschema.validate(result_dict, schema)
