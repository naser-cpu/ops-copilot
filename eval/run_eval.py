#!/usr/bin/env python3
"""
Evaluation harness for the Agentic Lab Assistant.

Runs test prompts through the agent and validates outputs against schema.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import jsonschema

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# noqa: E402 - imports after sys.path modification
from api.database import get_db_session  # noqa: E402
from worker.agent.executor import execute_plan  # noqa: E402
from worker.agent.planner import create_plan  # noqa: E402


@dataclass
class EvalResult:
    """Result of a single evaluation."""

    prompt_id: str
    prompt: str
    passed: bool
    errors: list[str]
    result: dict | None


def load_prompts(prompts_file: Path) -> list[dict]:
    """Load evaluation prompts from JSONL file."""
    prompts = []
    with open(prompts_file) as f:
        for line in f:
            line = line.strip()
            if line:
                prompts.append(json.loads(line))
    return prompts


def load_schema(schema_file: Path) -> dict:
    """Load JSON schema for validation."""
    with open(schema_file) as f:
        return json.load(f)


def validate_result(
    result: dict,
    schema: dict,
    expects_docs: bool,
    expects_incidents: bool,
) -> list[str]:
    """
    Validate a result against schema and content expectations.

    Returns list of error messages (empty if valid).
    """
    errors = []

    # Validate against JSON schema
    try:
        jsonschema.validate(result, schema)
    except jsonschema.ValidationError as e:
        errors.append(f"Schema validation failed: {e.message}")

    # Check required fields exist and have content
    if not result.get("summary"):
        errors.append("Summary is empty")

    if not result.get("steps"):
        errors.append("Steps list is empty")

    # Check sources based on expectations
    sources = result.get("sources", [])

    if expects_docs or expects_incidents:
        if not sources:
            errors.append("Expected sources but got empty list")

    if expects_docs:
        doc_sources = [s for s in sources if s.endswith(".md")]
        if not doc_sources:
            # This is a soft warning, not a hard failure
            # Some prompts might legitimately find results from incidents only
            pass

    if expects_incidents:
        incident_sources = [s for s in sources if s.startswith("INC-")]
        if not incident_sources:
            # This is a soft warning
            pass

    return errors


def run_single_eval(
    prompt_data: dict,
    schema: dict,
) -> EvalResult:
    """Run evaluation for a single prompt."""
    prompt_id = prompt_data["id"]
    prompt = prompt_data["prompt"]
    expects_docs = prompt_data.get("expects_docs", True)
    expects_incidents = prompt_data.get("expects_incidents", True)

    errors = []
    result_dict = None

    try:
        # Create plan
        plan = create_plan(prompt)

        # Validate plan
        if not plan.steps:
            errors.append("Planner produced empty plan")

        # Execute plan
        with get_db_session() as db:
            result, tool_calls = execute_plan(prompt, plan, db)
            result_dict = result.model_dump()

        # Validate result
        validation_errors = validate_result(
            result_dict,
            schema,
            expects_docs,
            expects_incidents,
        )
        errors.extend(validation_errors)

    except Exception as e:
        errors.append(f"Execution error: {str(e)}")

    return EvalResult(
        prompt_id=prompt_id,
        prompt=prompt,
        passed=len(errors) == 0,
        errors=errors,
        result=result_dict,
    )


def run_all_evals() -> tuple[list[EvalResult], dict]:
    """
    Run all evaluations and return results.

    Returns:
        Tuple of (list of EvalResults, summary dict)
    """
    # Find eval files
    eval_dir = Path(__file__).parent
    prompts_file = eval_dir / "prompts.jsonl"
    schema_file = eval_dir / "schema.json"

    if not prompts_file.exists():
        raise FileNotFoundError(f"Prompts file not found: {prompts_file}")

    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")

    # Load data
    prompts = load_prompts(prompts_file)
    schema = load_schema(schema_file)

    print(f"Running {len(prompts)} evaluations...")
    print("=" * 60)

    results = []
    for i, prompt_data in enumerate(prompts):
        print(f"\n[{i+1}/{len(prompts)}] {prompt_data['id']}: {prompt_data['prompt'][:50]}...")

        result = run_single_eval(prompt_data, schema)
        results.append(result)

        if result.passed:
            print("  ✓ PASSED")
        else:
            print("  ✗ FAILED")
            for error in result.errors:
                print(f"    - {error}")

    # Calculate summary
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    pass_rate = (passed / len(results)) * 100 if results else 0

    summary = {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
    }

    return results, summary


def main():
    """Main entry point for evaluation."""
    print("=" * 60)
    print("Agentic Lab Assistant - Evaluation Harness")
    print("=" * 60)

    try:
        results, summary = run_all_evals()
    except Exception as e:
        print(f"\n❌ Evaluation failed with error: {e}")
        sys.exit(1)

    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total:     {summary['total']}")
    print(f"Passed:    {summary['passed']}")
    print(f"Failed:    {summary['failed']}")
    print(f"Pass Rate: {summary['pass_rate']:.1f}%")

    # Print failed prompts
    if summary["failed"] > 0:
        print("\nFailed Prompts:")
        for result in results:
            if not result.passed:
                print(f"  - {result.prompt_id}: {result.prompt[:50]}...")
                for error in result.errors:
                    print(f"      Error: {error}")

    # Exit with appropriate code
    if summary["pass_rate"] < 70:
        print("\n❌ Evaluation FAILED (pass rate < 70%)")
        sys.exit(1)
    else:
        print("\n✓ Evaluation PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
