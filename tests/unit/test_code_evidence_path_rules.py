"""Tests for generic code evidence path role scoring."""

from bug_resolver.rules.code_evidence_path_rules import CodeEvidencePathRules


def test_support_path_is_penalized_when_not_mentioned() -> None:
    rules = CodeEvidencePathRules()

    score = rules.support_adjustment(
        "src/ui/retrieval_inspector.py",
        {"reranker", "ranking", "quality"},
        penalty=-2.0,
        mention_bonus=0.5,
    )

    assert score < 0


def test_support_path_is_allowed_when_query_mentions_role() -> None:
    rules = CodeEvidencePathRules()

    score = rules.support_adjustment(
        "src/ui/retrieval_inspector.py",
        {"ui", "inspector", "ranking", "quality"},
        penalty=-2.0,
        mention_bonus=0.5,
    )

    assert score > 0


def test_roles_detect_eval_demo_notebook_script_and_debug_paths() -> None:
    rules = CodeEvidencePathRules()

    assert [role.name for role in rules.roles_for_path("eval/compare.py")] == ["evaluation"]
    assert [role.name for role in rules.roles_for_path("examples/demo_app.py")] == [
        "demo"
    ]
    assert [role.name for role in rules.roles_for_path("notebooks/analysis.ipynb")] == [
        "notebook"
    ]
    assert [role.name for role in rules.roles_for_path("scripts/rebuild_index.py")] == [
        "script"
    ]
    assert [role.name for role in rules.roles_for_path("tools/debug_inspector.py")] == [
        "debug_tool"
    ]


def test_tokens_split_snake_case_for_role_matching() -> None:
    rules = CodeEvidencePathRules()

    assert {"front_end", "front", "end"} <= rules.tokens("front_end/retrieval_debug.py")
