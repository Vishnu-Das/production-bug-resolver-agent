"""Helpers for generating readable trace, report, and recommendation IDs."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


def new_incident_id(prefix: str = "INC") -> str:
    """
    Generate a readable incident id.

    Example:
        INC-20260518-8F3A91C2
    """

    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = uuid4().hex[:8].upper()
    return f"{prefix}-{date_part}-{random_part}"


def new_agent_decision_id(prefix: str = "DEC") -> str:
    """
    Generate a readable supervisor decision id.

    Example:
        DEC-20260518-8F3A91C2
    """

    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = uuid4().hex[:8].upper()
    return f"{prefix}-{date_part}-{random_part}"


def new_agent_execution_id(prefix: str = "RUN") -> str:
    """
    Generate a readable agent execution id.

    Example:
        RUN-20260518-8F3A91C2
    """

    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = uuid4().hex[:8].upper()
    return f"{prefix}-{date_part}-{random_part}"


def new_hypothesis_id(prefix: str = "HYP") -> str:
    """
    Generate a readable hypothesis id.

    Example:
        HYP-20260518-8F3A91C2
    """

    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = uuid4().hex[:8].upper()
    return f"{prefix}-{date_part}-{random_part}"


def new_rca_report_id(prefix: str = "RCA") -> str:
    """
    Generate a readable RCA report id.

    Example:
        RCA-20260518-8F3A91C2
    """

    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = uuid4().hex[:8].upper()
    return f"{prefix}-{date_part}-{random_part}"


def new_evaluation_id(prefix: str = "EVAL") -> str:
    """
    Generate a readable evidence evaluation id.

    Example:
        EVAL-20260518-8F3A91C2
    """

    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = uuid4().hex[:8].upper()
    return f"{prefix}-{date_part}-{random_part}"


def new_guardrail_id(prefix: str = "GRD") -> str:
    """
    Generate a readable guardrail decision id.

    Example:
        GRD-20260518-8F3A91C2
    """

    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = uuid4().hex[:8].upper()
    return f"{prefix}-{date_part}-{random_part}"


def new_recommendation_id(prefix: str = "SOL") -> str:
    """
    Generate a readable solution recommendation id.

    Example:
        SOL-20260518-8F3A91C2
    """

    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = uuid4().hex[:8].upper()
    return f"{prefix}-{date_part}-{random_part}"


def new_patch_suggestion_id(prefix: str = "PATCH") -> str:
    """
    Generate a readable patch suggestion id.

    Example:
        PATCH-20260518-8F3A91C2
    """

    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = uuid4().hex[:8].upper()
    return f"{prefix}-{date_part}-{random_part}"
