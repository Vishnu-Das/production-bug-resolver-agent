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

def new_context_plan_id(prefix: str = "CTX") -> str:
    """
    Generate a readable context plan id.

    Example:
        CTX-20260518-8F3A91C2
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

def new_recommendation_id(prefix: str = "SOL") -> str:
    """
    Generate a readable solution recommendation id.

    Example:
        SOL-20260518-8F3A91C2
    """

    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = uuid4().hex[:8].upper()
    return f"{prefix}-{date_part}-{random_part}"