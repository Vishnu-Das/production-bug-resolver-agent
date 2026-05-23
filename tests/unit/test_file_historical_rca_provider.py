"""Tests for file-backed historical RCA retrieval."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bug_resolver.providers.history import FileHistoricalRCAProvider


def write_rca(
    reports_dir: Path,
    incident_id: str,
    *,
    title: str,
    root_cause: str,
    confidence_score: float = 0.8,
) -> None:
    report_dir = reports_dir / "incidents" / incident_id
    report_dir.mkdir(parents=True)
    (report_dir / "rca.json").write_text(
        json.dumps(
            {
                "report_id": f"RCA-{incident_id}",
                "incident_id": incident_id,
                "title": title,
                "incident_summary": title,
                "root_cause": root_cause,
                "technical_explanation": root_cause,
                "evidence_ids": ["ev-log", "ev-code"],
                "confidence_score": confidence_score,
                "confidence_reason": "Prior evidence was sufficient.",
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_file_historical_rca_provider_returns_ranked_matches(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    write_rca(
        reports_dir,
        "INC-OLD-1",
        title="Duplicate documents after upload",
        root_cause="Upload deduplication used filename instead of content_hash.",
    )
    write_rca(
        reports_dir,
        "INC-OLD-2",
        title="Routing exception",
        root_cause="Router validation rejected an unsupported strategy.",
    )

    provider = FileHistoricalRCAProvider(reports_dir)

    results = await provider.search_history(
        ["duplicate upload content_hash recurrence"],
        current_incident_id="INC-NEW",
    )

    assert [result.incident_id for result in results] == ["INC-OLD-1"]
    assert set(results[0].matched_signals) >= {"content_hash", "duplicate", "upload"}
    assert results[0].relevance_score > 0


@pytest.mark.asyncio
async def test_file_historical_rca_provider_skips_current_incident(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    write_rca(
        reports_dir,
        "INC-001",
        title="Duplicate documents after upload",
        root_cause="Upload deduplication used filename instead of content_hash.",
    )

    provider = FileHistoricalRCAProvider(reports_dir)

    results = await provider.search_history(
        ["duplicate upload content_hash"],
        current_incident_id="INC-001",
    )

    assert results == []
