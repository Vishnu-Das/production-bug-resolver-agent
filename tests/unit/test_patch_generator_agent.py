"""Tests for analyze-only patch diff generation agent."""

from __future__ import annotations

import pytest

from bug_resolver.agents import PatchGeneratorAgent, PatchGeneratorInput
from bug_resolver.schemas import (
    EvidenceItem,
    EvidenceSourceType,
    FilePatch,
    PatchGenerationResult,
    RCAReport,
)
from bug_resolver.schemas.solution import SolutionRecommendation


class FakePatchContextProvider:
    def __init__(self, files: dict[str, str]) -> None:
        self.files = files

    async def read_file(self, file_path: str) -> str | None:
        return self.files.get(file_path)


class FakeLLMClient:
    def __init__(self, result: PatchGenerationResult) -> None:
        self.result = result
        self.prompt = ""

    async def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        return "unused"

    async def generate_structured(self, prompt, output_schema, *, system_prompt=None):
        self.prompt = prompt
        return self.result


def build_rca_report() -> RCAReport:
    return RCAReport(
        report_id="RCA-001",
        incident_id="INC-001",
        title="RCA",
        incident_summary="Summary.",
        root_cause="Handler returns the wrong value.",
        technical_explanation="src/app.py contains the failing branch.",
        evidence_ids=["evidence-src/app.py:handler"],
        confidence_score=0.8,
        confidence_reason="Code and logs agree.",
        immediate_fix="Return the corrected value.",
        tests_to_add=["Add handler regression test."],
    )


def build_upload_rca_report() -> RCAReport:
    return RCAReport(
        report_id="RCA-007",
        incident_id="INC-007",
        title="RCA for duplicate uploads",
        incident_summary="Users see duplicate records after upload.",
        root_cause="Upload dedupe uses filename instead of content_hash identity.",
        technical_explanation="The ingestion path accepts duplicate content.",
        evidence_ids=[
            "EVID-LOG-001",
            "graph-src/rag/routing/rule_based.py:RuleBasedRouterStrategy.route",
            "evidence-kb-upload-ingestion",
        ],
        confidence_score=0.8,
        confidence_reason="Logs and KB agree.",
        immediate_fix="Use content hash before ingestion.",
    )


def build_solution() -> SolutionRecommendation:
    return SolutionRecommendation(
        recommendation_id="SOL-001",
        incident_id="INC-001",
        rca_report_id="RCA-001",
        summary="Fix handler output.",
        immediate_steps=["Update the handler return value."],
        confidence_score=0.8,
        evidence_ids=["evidence-src/app.py:handler"],
    )


def build_upload_solution() -> SolutionRecommendation:
    return SolutionRecommendation(
        recommendation_id="SOL-007",
        incident_id="INC-007",
        rca_report_id="RCA-007",
        summary="Fix duplicate upload handling.",
        immediate_steps=["Use content hash as duplicate identity before ingestion."],
        confidence_score=0.8,
        evidence_ids=[
            "graph-src/rag/routing/rule_based.py:RuleBasedRouterStrategy.route",
            "evidence-kb-upload-ingestion",
        ],
    )


def build_input() -> PatchGeneratorInput:
    return PatchGeneratorInput(
        rca_report=build_rca_report(),
        solution_recommendation=build_solution(),
        affected_files=["src/app.py"],
        evidence_ids=["evidence-src/app.py:handler"],
    )


@pytest.mark.asyncio
async def test_patch_generator_skips_when_no_files_are_readable() -> None:
    agent = PatchGeneratorAgent(
        patch_context_provider=FakePatchContextProvider({}),
        llm_client=FakeLLMClient(PatchGenerationResult()),
    )

    result = await agent.run(build_input())

    assert result.generated_diff is False
    assert "no safe code-backed affected files" in result.warnings[0]
    assert result.open_questions == [
        "Which source file owns the implementation change for this incident?"
    ]


@pytest.mark.asyncio
async def test_patch_generator_skips_when_llm_is_not_configured() -> None:
    agent = PatchGeneratorAgent(
        patch_context_provider=FakePatchContextProvider({"src/app.py": "old\n"}),
    )

    result = await agent.run(build_input())

    assert result.generated_diff is False
    assert result.file_patches == []
    assert "no LLM client was configured" in result.warnings[0]


@pytest.mark.asyncio
async def test_patch_generator_returns_validated_llm_diff() -> None:
    llm_result = PatchGenerationResult(
        file_patches=[
            FilePatch(
                file_path="src/app.py",
                unified_diff=(
                    "--- a/src/app.py\n"
                    "+++ b/src/app.py\n"
                    "@@\n"
                    "-return 'old'\n"
                    "+return 'new'\n"
                ),
                reason="Correct the handler return value.",
                evidence_ids=["evidence-src/app.py:handler"],
                confidence_score=0.75,
            ),
            FilePatch(
                file_path="src/invented.py",
                unified_diff="--- a/src/invented.py\n+++ b/src/invented.py\n",
                reason="Invented file.",
                confidence_score=0.2,
            ),
        ]
    )
    llm_client = FakeLLMClient(llm_result)
    agent = PatchGeneratorAgent(
        patch_context_provider=FakePatchContextProvider({"src/app.py": "return 'old'\n"}),
        llm_client=llm_client,
    )

    result = await agent.run(build_input())

    assert result.generated_diff is True
    assert [patch.file_path for patch in result.file_patches] == ["src/app.py"]
    assert any("unreadable or unapproved" in warning for warning in result.warnings)
    assert "File: src/app.py" in llm_client.prompt


@pytest.mark.asyncio
async def test_patch_generator_skips_graph_only_upload_routing_targets() -> None:
    llm_client = FakeLLMClient(
        PatchGenerationResult(
            file_patches=[
                FilePatch(
                    file_path="src/rag/routing/rule_based.py",
                    unified_diff=(
                        "--- a/src/rag/routing/rule_based.py\n"
                        "+++ b/src/rag/routing/rule_based.py\n"
                        "@@\n"
                        "-old\n"
                        "+new\n"
                    ),
                    reason="Wrong upload owner.",
                    confidence_score=0.8,
                )
            ]
        )
    )
    agent = PatchGeneratorAgent(
        patch_context_provider=FakePatchContextProvider(
            {"src/rag/routing/rule_based.py": "old\n"}
        ),
        llm_client=llm_client,
    )

    result = await agent.run(
        PatchGeneratorInput(
            rca_report=build_upload_rca_report(),
            solution_recommendation=build_upload_solution(),
            affected_files=["src/rag/routing/rule_based.py"],
            evidence_ids=[
                "graph-src/rag/routing/rule_based.py:RuleBasedRouterStrategy.route",
                "evidence-kb-upload-ingestion",
            ],
        )
    )

    assert result.generated_diff is False
    assert result.file_patches == []
    assert "no safe code-backed affected files" in result.warnings[0]
    assert llm_client.prompt == ""


@pytest.mark.asyncio
async def test_patch_generator_skips_when_only_graph_and_test_evidence_exists() -> None:
    llm_client = FakeLLMClient(PatchGenerationResult())
    agent = PatchGeneratorAgent(
        patch_context_provider=FakePatchContextProvider(
            {
                "src/services/upload_service.py": "def upload(): pass\n",
                "tests/test_upload.py": "def test_upload(): pass\n",
            }
        ),
        llm_client=llm_client,
    )

    result = await agent.run(
        PatchGeneratorInput(
            rca_report=build_upload_rca_report(),
            solution_recommendation=build_upload_solution(),
            affected_files=["src/services/upload_service.py", "tests/test_upload.py"],
            evidence_ids=[
                "graph-src/services/upload_service.py:upload",
                "evidence-tests/test_upload.py:test_upload",
            ],
        )
    )

    assert result.generated_diff is False
    assert result.file_patches == []
    assert "no safe code-backed affected files" in result.warnings[0]
    assert llm_client.prompt == ""


@pytest.mark.asyncio
async def test_patch_generator_allows_readable_code_backed_patch_without_domain_blocklist() -> None:
    llm_client = FakeLLMClient(
        PatchGenerationResult(
            file_patches=[
                FilePatch(
                    file_path="src/rag/routing/rule_based.py",
                    unified_diff=(
                        "--- a/src/rag/routing/rule_based.py\n"
                        "+++ b/src/rag/routing/rule_based.py\n"
                        "@@\n"
                        "-return old\n"
                        "+return new\n"
                    ),
                    reason="Wrong upload owner.",
                    confidence_score=0.8,
                )
            ]
        )
    )
    agent = PatchGeneratorAgent(
        patch_context_provider=FakePatchContextProvider(
            {"src/rag/routing/rule_based.py": "return old\n"}
        ),
        llm_client=llm_client,
    )

    result = await agent.run(
        PatchGeneratorInput(
            rca_report=build_upload_rca_report(),
            solution_recommendation=build_upload_solution(),
            affected_files=["src/rag/routing/rule_based.py"],
            evidence_ids=[
                "evidence-src/rag/routing/rule_based.py:RuleBasedRouterStrategy.route",
            ],
        )
    )

    assert result.generated_diff is True
    assert [patch.file_path for patch in result.file_patches] == [
        "src/rag/routing/rule_based.py"
    ]
    assert result.warnings == []


@pytest.mark.asyncio
async def test_patch_generator_authorizes_structured_exact_code_evidence() -> None:
    llm_client = FakeLLMClient(
        PatchGenerationResult(
            file_patches=[
                FilePatch(
                    file_path="src/services/upload_service.py",
                    unified_diff=(
                        "--- a/src/services/upload_service.py\n"
                        "+++ b/src/services/upload_service.py\n"
                        "@@\n"
                        "-if filename in processed_uploads:\n"
                        "+if content_hash in processed_uploads:\n"
                    ),
                    reason="Use stable content identity.",
                    confidence_score=0.75,
                )
            ]
        )
    )
    agent = PatchGeneratorAgent(
        patch_context_provider=FakePatchContextProvider(
            {
                "src/services/upload_service.py": (
                    "if filename in processed_uploads:\n    return\n"
                )
            }
        ),
        llm_client=llm_client,
    )

    result = await agent.run(
        PatchGeneratorInput(
            rca_report=build_upload_rca_report(),
            solution_recommendation=build_upload_solution(),
            affected_files=["src/services/upload_service.py"],
            evidence_ids=["EVID-EXACT-OWNER"],
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-EXACT-OWNER",
                    source_type=EvidenceSourceType.CODE,
                    source_name="src/services/upload_service.py",
                    file_path="src/services/upload_service.py",
                    content="if filename in processed_uploads:\n    return",
                    metadata={"retrieval_source_type": "code_exact"},
                )
            ],
        )
    )

    assert result.generated_diff is True
    assert [patch.file_path for patch in result.file_patches] == [
        "src/services/upload_service.py"
    ]
    assert "File: src/services/upload_service.py" in llm_client.prompt


@pytest.mark.asyncio
async def test_patch_generator_does_not_modify_target_files() -> None:
    files = {"src/app.py": "return 'old'\n"}
    agent = PatchGeneratorAgent(
        patch_context_provider=FakePatchContextProvider(files),
        llm_client=FakeLLMClient(
            PatchGenerationResult(
                file_patches=[
                    FilePatch(
                        file_path="src/app.py",
                        unified_diff=(
                            "--- a/src/app.py\n"
                            "+++ b/src/app.py\n"
                            "@@\n"
                            "-return 'old'\n"
                            "+return 'new'\n"
                        ),
                        reason="Suggest only.",
                        confidence_score=0.8,
                    )
                ]
            )
        ),
    )

    result = await agent.run(build_input())

    assert result.generated_diff is True
    assert files["src/app.py"] == "return 'old'\n"
