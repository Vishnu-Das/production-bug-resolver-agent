"""Tests for safe patch generation validation rules."""

from __future__ import annotations

from bug_resolver.rules import PatchGenerationRules
from bug_resolver.schemas import FilePatch, PatchGenerationResult


def test_patch_generation_rules_allows_only_affected_readable_files() -> None:
    rules = PatchGenerationRules()

    allowed_files = rules.allowed_patch_files(
        affected_files=["src/app.py", "src/missing.py"],
        readable_files={"src/app.py": "print('hello')\n"},
    )

    assert allowed_files == {"src/app.py"}


def test_patch_generation_rules_keeps_valid_patch() -> None:
    rules = PatchGenerationRules()
    result = PatchGenerationResult(
        file_patches=[
            FilePatch(
                file_path="src/app.py",
                unified_diff=(
                    "--- a/src/app.py\n"
                    "+++ b/src/app.py\n"
                    "@@\n"
                    "-old\n"
                    "+new\n"
                ),
                reason="Fix the failing branch.",
                evidence_ids=["evidence-src/app.py:handler"],
                confidence_score=0.8,
            )
        ],
    )

    validated = rules.validate_patch_result(
        result=result,
        allowed_files={"src/app.py"},
    )

    assert validated.generated_diff is True
    assert len(validated.file_patches) == 1
    assert validated.warnings == []


def test_patch_generation_rules_rejects_invented_file_and_empty_diff() -> None:
    rules = PatchGenerationRules()
    result = PatchGenerationResult(
        file_patches=[
            FilePatch(
                file_path="src/invented.py",
                unified_diff="--- a/src/invented.py\n+++ b/src/invented.py\n",
                reason="Invented file.",
                confidence_score=0.4,
            ),
            FilePatch(
                file_path="src/app.py",
                unified_diff="",
                reason="Empty diff.",
                confidence_score=0.4,
            ),
        ],
    )

    validated = rules.validate_patch_result(
        result=result,
        allowed_files={"src/app.py"},
    )

    assert validated.generated_diff is False
    assert validated.file_patches == []
    assert any("unreadable or unapproved" in warning for warning in validated.warnings)
    assert any("empty diff" in warning for warning in validated.warnings)


def test_patch_generation_rules_rejects_mismatched_diff_header() -> None:
    rules = PatchGenerationRules()
    result = PatchGenerationResult(
        file_patches=[
            FilePatch(
                file_path="src/app.py",
                unified_diff="--- a/src/other.py\n+++ b/src/other.py\n@@\n-old\n+new\n",
                reason="Wrong file header.",
                confidence_score=0.4,
            )
        ],
    )

    validated = rules.validate_patch_result(
        result=result,
        allowed_files={"src/app.py"},
    )

    assert validated.generated_diff is False
    assert validated.file_patches == []
    assert any("headers do not match" in warning for warning in validated.warnings)


def test_patch_generation_rules_normalizes_apply_patch_format() -> None:
    rules = PatchGenerationRules()
    result = PatchGenerationResult(
        file_patches=[
            FilePatch(
                file_path="src/services/upload_service.py",
                unified_diff=(
                    "*** Begin Patch\n"
                    "*** Update File: src/services/upload_service.py\n"
                    "@@\n"
                    "-    if filename in st.session_state.processed_uploads:\n"
                    "+    if content_hash in st.session_state.processed_uploads:\n"
                    "         return\n"
                    "*** End Patch"
                ),
                reason="Use content identity for duplicate detection.",
                confidence_score=0.7,
            )
        ],
    )

    validated = rules.validate_patch_result(
        result=result,
        allowed_files={"src/services/upload_service.py"},
    )

    assert validated.generated_diff is True
    assert len(validated.file_patches) == 1
    assert validated.file_patches[0].unified_diff.startswith(
        "--- a/src/services/upload_service.py\n+++ b/src/services/upload_service.py\n"
    )
    assert "*** Begin Patch" not in validated.file_patches[0].unified_diff
    assert validated.warnings == []


def test_patch_generation_rules_normalizes_fenced_apply_patch_format() -> None:
    rules = PatchGenerationRules()
    result = PatchGenerationResult(
        file_patches=[
            FilePatch(
                file_path="src/services/upload_service.py",
                unified_diff=(
                    "```patch\n"
                    "*** Begin Patch\n"
                    "*** Update File: .\\src\\services\\upload_service.py\n"
                    "@@\n"
                    "-    st.session_state.processed_uploads.add(filename)\n"
                    "+    st.session_state.processed_uploads.add(content_hash)\n"
                    "*** End Patch\n"
                    "```"
                ),
                reason="Use content identity for duplicate detection.",
                confidence_score=0.7,
            )
        ],
    )

    validated = rules.validate_patch_result(
        result=result,
        allowed_files={"src/services/upload_service.py"},
    )

    assert validated.generated_diff is True
    assert len(validated.file_patches) == 1
    assert validated.file_patches[0].unified_diff.startswith(
        "--- a/src/services/upload_service.py\n+++ b/src/services/upload_service.py\n"
    )
    assert "```" not in validated.file_patches[0].unified_diff
    assert validated.warnings == []


def test_patch_generation_rules_rejects_apply_patch_add_file() -> None:
    rules = PatchGenerationRules()
    result = PatchGenerationResult(
        file_patches=[
            FilePatch(
                file_path="src/app.py",
                unified_diff=(
                    "*** Begin Patch\n"
                    "*** Add File: src/app.py\n"
                    "+print('invented')\n"
                    "*** End Patch"
                ),
                reason="Invent a file.",
                confidence_score=0.4,
            )
        ],
    )

    validated = rules.validate_patch_result(
        result=result,
        allowed_files={"src/app.py"},
    )

    assert validated.generated_diff is False
    assert validated.file_patches == []
    assert any("headers do not match" in warning for warning in validated.warnings)


def test_patch_generation_rules_rejects_placeholder_implementation() -> None:
    rules = PatchGenerationRules()
    result = PatchGenerationResult(
        file_patches=[
            FilePatch(
                file_path="src/app.py",
                unified_diff=(
                    "--- a/src/app.py\n"
                    "+++ b/src/app.py\n"
                    "@@\n"
                    "+RERANKING_MODEL_NAME = ...  # require config here\n"
                    "+def upload_exists():\n"
                    "+    \"\"\"Implementation needed.\"\"\"\n"
                    "+    pass\n"
                    "+# ... remaining code unchanged\n"
                ),
                reason="Placeholder implementation.",
                confidence_score=0.4,
            )
        ],
    )

    validated = rules.validate_patch_result(
        result=result,
        allowed_files={"src/app.py"},
    )

    assert validated.generated_diff is False
    assert validated.file_patches == []
    assert any("placeholder" in warning for warning in validated.warnings)


def test_patch_generation_rules_rejects_signature_changing_single_file_patch() -> None:
    rules = PatchGenerationRules()
    result = PatchGenerationResult(
        file_patches=[
            FilePatch(
                file_path="src/router.py",
                unified_diff=(
                    "--- a/src/router.py\n"
                    "+++ b/src/router.py\n"
                    "@@\n"
                    "-def route(query: str) -> RouterResult:\n"
                    "+def route(query: str, content: bytes) -> RouterResult:\n"
                    "     return RouterResult(strategy='hybrid')\n"
                ),
                reason="Changes public signature.",
                confidence_score=0.4,
            )
        ],
    )

    validated = rules.validate_patch_result(
        result=result,
        allowed_files={"src/router.py"},
    )

    assert validated.generated_diff is False
    assert validated.file_patches == []
    assert any("function signature" in warning for warning in validated.warnings)


def test_patch_generation_rules_allows_readable_approved_patch_without_domain_blocklist() -> None:
    rules = PatchGenerationRules()
    result = PatchGenerationResult(
        file_patches=[
            FilePatch(
                file_path="src/rag/routing/rule_based.py",
                unified_diff=(
                    "--- a/src/rag/routing/rule_based.py\n"
                    "+++ b/src/rag/routing/rule_based.py\n"
                    "@@\n"
                    "-return route\n"
                    "+return route\n"
                ),
                reason="Wrong owner.",
                confidence_score=0.4,
            )
        ],
    )

    validated = rules.validate_patch_result(
        result=result,
        allowed_files={"src/rag/routing/rule_based.py"},
        incident_context="duplicate upload content_hash ingestion bug",
    )

    assert validated.generated_diff is True
    assert [patch.file_path for patch in validated.file_patches] == [
        "src/rag/routing/rule_based.py"
    ]
    assert validated.warnings == []


def test_patch_generation_rules_generated_diff_false_when_all_patches_rejected() -> None:
    rules = PatchGenerationRules()
    result = PatchGenerationResult(
        generated_diff=True,
        file_patches=[
            FilePatch(
                file_path="src/app.py",
                unified_diff="",
                reason="Empty diff.",
                confidence_score=0.4,
            )
        ],
        test_patches=[
            FilePatch(
                file_path="src/test_app.py",
                unified_diff="--- a/src/other.py\n+++ b/src/other.py\n",
                reason="Mismatched header.",
                confidence_score=0.4,
            )
        ],
    )

    validated = rules.validate_patch_result(
        result=result,
        allowed_files={"src/app.py", "src/test_app.py"},
    )

    assert validated.generated_diff is False
    assert validated.file_patches == []
    assert validated.test_patches == []
