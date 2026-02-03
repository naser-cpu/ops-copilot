"""Planner module that creates structured execution plans."""

import json
import logging
import os
import re

import httpx

from api.schemas import AgentPlan, PlanStep

logger = logging.getLogger(__name__)

# Keywords that suggest we need to search documentation
DOC_KEYWORDS = [
    "how",
    "what",
    "guide",
    "tutorial",
    "troubleshoot",
    "debug",
    "fix",
    "solve",
    "help",
    "explain",
    "documentation",
    "runbook",
    "procedure",
    "steps",
    "deploy",
    "deployment",
    "database",
    "connection",
    "timeout",
    "error",
    "configure",
    "setup",
    "install",
]

# Keywords that suggest we need to query incidents
INCIDENT_KEYWORDS = [
    "incident",
    "outage",
    "issue",
    "problem",
    "failure",
    "down",
    "alert",
    "critical",
    "recent",
    "past",
    "history",
    "similar",
    "previous",
    "resolved",
    "root cause",
    "postmortem",
]


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from the input text."""
    # Simple keyword extraction
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    # Filter common stop words
    stop_words = {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "had",
        "her",
        "was",
        "one",
        "our",
        "out",
        "has",
        "have",
        "been",
        "would",
        "could",
        "there",
        "their",
        "will",
        "when",
        "who",
        "with",
        "this",
        "that",
        "from",
        "how",
    }
    return [w for w in words if w not in stop_words]


def _needs_docs(text: str) -> bool:
    """Determine if the request needs documentation search."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in DOC_KEYWORDS)


def _needs_incidents(text: str) -> bool:
    """Determine if the request needs incident search."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in INCIDENT_KEYWORDS)


def _create_deterministic_plan(text: str) -> AgentPlan:
    """
    Create a deterministic plan based on keyword matching.
    This is the default stub that doesn't require an LLM.
    """
    keywords = _extract_keywords(text)
    query = " ".join(keywords[:5]) if keywords else text[:50]

    steps = []
    step_num = 1

    # Determine which tools to use
    needs_docs = _needs_docs(text)
    needs_incidents = _needs_incidents(text)

    # If neither is clearly needed, search both
    if not needs_docs and not needs_incidents:
        needs_docs = True
        needs_incidents = True

    if needs_docs:
        steps.append(
            PlanStep(
                step_number=step_num,
                action="Search documentation for relevant runbooks",
                tool="search_docs",
                tool_input=query,
            )
        )
        step_num += 1

    if needs_incidents:
        steps.append(
            PlanStep(
                step_number=step_num,
                action="Query incident database for related incidents",
                tool="query_incidents",
                tool_input=query,
            )
        )
        step_num += 1

    steps.append(
        PlanStep(
            step_number=step_num,
            action="Synthesize findings and provide recommendation",
            tool=None,
            tool_input=None,
        )
    )

    reasoning = (
        f"Based on the request, I identified the following needs: "
        f"{'documentation search' if needs_docs else ''}"
        f"{' and ' if needs_docs and needs_incidents else ''}"
        f"{'incident history lookup' if needs_incidents else ''}. "
        f"Key topics: {', '.join(keywords[:5]) if keywords else 'general inquiry'}."
    )

    return AgentPlan(reasoning=reasoning, steps=steps)


def _create_llm_plan(text: str) -> AgentPlan:
    """
    Create a plan using a real LLM.
    Requires LLM_API_KEY environment variable.
    """
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL", "gpt-4")

    if not api_key:
        logger.warning("LLM_API_KEY not set, falling back to deterministic planner")
        return _create_deterministic_plan(text)

    prompt = f"""You are a lab assistant planner. Given a user request, create a structured plan to answer it.

Available tools:
1. search_docs(query) - Search documentation/runbooks for relevant information
2. query_incidents(query) - Search incident database for similar past issues

User request: {text}

Respond with a JSON object containing:
- reasoning: Why you chose these steps
- steps: Array of step objects, each with:
  - step_number: int
  - action: Description of what to do
  - tool: "search_docs", "query_incidents", or null (for synthesis step)
  - tool_input: Query string for the tool, or null

Example response:
{{
  "reasoning": "The user is asking about database issues, so I'll search docs and check past incidents.",
  "steps": [
    {{"step_number": 1, "action": "Search for database troubleshooting docs", "tool": "search_docs", "tool_input": "database connection troubleshooting"}},
    {{"step_number": 2, "action": "Find related incidents", "tool": "query_incidents", "tool_input": "database connection"}},
    {{"step_number": 3, "action": "Synthesize findings", "tool": null, "tool_input": null}}
  ]
}}"""

    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        plan_data = json.loads(content)
        return AgentPlan(**plan_data)
    except Exception as e:
        logger.error(f"LLM planning failed: {e}, falling back to deterministic")
        return _create_deterministic_plan(text)


def create_plan(text: str) -> AgentPlan:
    """
    Create an execution plan for the given request.

    Uses deterministic planning by default, or LLM if USE_REAL_LLM=true.

    Args:
        text: The user's request text

    Returns:
        An AgentPlan with reasoning and steps
    """
    use_llm = os.getenv("USE_REAL_LLM", "false").lower() == "true"

    if use_llm:
        logger.info("Using LLM planner")
        return _create_llm_plan(text)
    else:
        logger.info("Using deterministic planner")
        return _create_deterministic_plan(text)
