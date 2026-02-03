"""Tool implementations for the agent."""

import logging
import os
import re
from pathlib import Path
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.models import Incident

logger = logging.getLogger(__name__)

# Path to runbooks directory
RUNBOOKS_DIR = Path(os.getenv("RUNBOOKS_DIR", "/app/data/runbooks"))


def search_docs(query: str) -> list[dict[str, Any]]:
    """
    Search documentation/runbooks for relevant content.

    Performs keyword-based search over markdown files in the runbooks directory.

    Args:
        query: Search query string

    Returns:
        List of matching documents with title, filename, snippet, and key_points
    """
    results = []
    keywords = set(re.findall(r"\b[a-zA-Z]{3,}\b", query.lower()))

    if not RUNBOOKS_DIR.exists():
        logger.warning(f"Runbooks directory not found: {RUNBOOKS_DIR}")
        return results

    for md_file in RUNBOOKS_DIR.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            content_lower = content.lower()

            # Calculate relevance score based on keyword matches
            matches = sum(1 for kw in keywords if kw in content_lower)

            if matches > 0:
                # Extract title (first # heading)
                title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                title = title_match.group(1) if title_match else md_file.stem

                # Extract snippet around first keyword match
                snippet = _extract_snippet(content, keywords)

                # Extract key points (bullet points)
                key_points = _extract_key_points(content)

                results.append(
                    {
                        "filename": md_file.name,
                        "title": title,
                        "snippet": snippet,
                        "key_points": key_points,
                        "relevance_score": matches,
                    }
                )

        except Exception as e:
            logger.error(f"Error reading {md_file}: {e}")
            continue

    # Sort by relevance score
    results.sort(key=lambda x: x["relevance_score"], reverse=True)

    return results[:5]  # Return top 5 results


def _extract_snippet(content: str, keywords: set[str], context_chars: int = 200) -> str:
    """Extract a snippet from content around the first keyword match."""
    content_lower = content.lower()

    for kw in keywords:
        pos = content_lower.find(kw)
        if pos != -1:
            start = max(0, pos - context_chars // 2)
            end = min(len(content), pos + context_chars // 2)

            # Adjust to word boundaries
            if start > 0:
                start = content.find(" ", start) + 1
            if end < len(content):
                end = content.rfind(" ", 0, end)

            snippet = content[start:end].strip()
            return f"...{snippet}..." if start > 0 else f"{snippet}..."

    # Fallback to beginning of content
    return content[:context_chars].strip() + "..."


def _extract_key_points(content: str) -> list[str]:
    """Extract bullet points or numbered items from content."""
    key_points = []

    # Match bullet points and numbered items
    patterns = [
        r"^[-*]\s+(.+)$",  # Bullet points
        r"^\d+\.\s+(.+)$",  # Numbered items
    ]

    for pattern in patterns:
        matches = re.findall(pattern, content, re.MULTILINE)
        key_points.extend(matches[:5])  # Limit per pattern

    return key_points[:10]  # Return max 10 key points


def query_incidents(query: str, db: Session) -> list[dict[str, Any]]:
    """
    Query the incidents database for relevant incidents.

    Performs SQL search against the incidents table.

    Args:
        query: Search query string
        db: Database session

    Returns:
        List of matching incidents with their details
    """
    results = []
    keywords = set(re.findall(r"\b[a-zA-Z]{3,}\b", query.lower()))

    if not keywords:
        # If no keywords, return recent incidents
        incidents = db.query(Incident).order_by(Incident.created_at.desc()).limit(5).all()
    else:
        # Build search conditions
        conditions = []
        for kw in keywords:
            pattern = f"%{kw}%"
            conditions.append(Incident.title.ilike(pattern))
            conditions.append(Incident.description.ilike(pattern))
            conditions.append(Incident.service.ilike(pattern))
            conditions.append(Incident.root_cause.ilike(pattern))
            conditions.append(Incident.resolution.ilike(pattern))

        incidents = (
            db.query(Incident)
            .filter(or_(*conditions))
            .order_by(Incident.created_at.desc())
            .limit(10)
            .all()
        )

    for incident in incidents:
        results.append(
            {
                "id": incident.id,
                "title": incident.title,
                "description": incident.description,
                "severity": incident.severity,
                "status": incident.status,
                "service": incident.service,
                "root_cause": incident.root_cause,
                "resolution": incident.resolution,
                "created_at": incident.created_at.isoformat() if incident.created_at else None,
                "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
                "tags": incident.tags,
            }
        )

    # Calculate relevance scores
    for result in results:
        score = 0
        searchable_text = " ".join(
            str(v).lower() for v in result.values() if v and isinstance(v, str)
        )
        for kw in keywords:
            if kw in searchable_text:
                score += 1
        result["relevance_score"] = score

    # Sort by relevance then recency
    results.sort(key=lambda x: (x.get("relevance_score", 0), x.get("created_at", "")), reverse=True)

    return results[:5]  # Return top 5 results
