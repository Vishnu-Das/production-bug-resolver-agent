"""LLM output validation signals shared by writer agents."""

ANALYZE_ONLY_COMPLETION_CLAIM_PHRASES = (
    "i fixed",
    "we fixed",
    "has been fixed",
    "was fixed",
    "is fixed",
    "deployed the fix",
    "deployed a fix",
    "merged the fix",
    "opened a pull request",
    "created a pull request",
)

PATCH_SUGGESTION_FORBIDDEN_PHRASES = (
    "i fixed",
    "we fixed",
    "has been fixed",
    "was fixed",
    "is fixed",
    "deployed",
    "committed",
    "created a pull request",
    "opened a pull request",
)

INTERNAL_EVIDENCE_PREFIXES = (
    "evidence-src/",
    "evidence-src\\",
    "evidence-tests/",
    "evidence-tests\\",
    "evidence-eval/",
    "evidence-eval\\",
    "evidence-docs/",
    "evidence-docs\\",
)

LOG_FINDING_MARKERS = (
    "log evidence",
    "logged",
    "request_id=",
    "trace_id=",
    "user feedback",
    "warning ",
    " error ",
    " info ",
)
