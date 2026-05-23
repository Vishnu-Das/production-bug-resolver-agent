"""Deterministic safety validation for generated patch diffs."""

from __future__ import annotations

from bug_resolver.schemas import FilePatch, PatchGenerationResult


PLACEHOLDER_IMPLEMENTATION_MARKERS = (
    "TODO",
    "Implementation needed",
    "... remaining code unchanged",
    "NotImplemented",
    "raise NotImplementedError",
)

UPLOAD_DEDUPE_TERMS = (
    "upload",
    "duplicate",
    "content_hash",
    "content hash",
    "ingestion",
)

UPLOAD_OWNERSHIP_TERMS = (
    "upload",
    "ingest",
    "ingestion",
    "dedup",
    "duplicate",
    "content_hash",
    "hash",
)

ROUTING_PATH_TERMS = (
    "router",
    "routing",
)


class PatchGenerationRules:
    """Validate analyze-only patch generation output before it reaches reports."""

    def allowed_patch_files(
        self,
        *,
        affected_files: list[str],
        readable_files: dict[str, str],
    ) -> set[str]:
        """Return affected files with exact readable contents."""
        affected = {self._normalize_path(file_path) for file_path in affected_files}
        readable = {self._normalize_path(file_path) for file_path in readable_files}
        return affected & readable

    def validate_patch_result(
        self,
        *,
        result: PatchGenerationResult,
        allowed_files: set[str],
        incident_context: str = "",
    ) -> PatchGenerationResult:
        """Strip unsafe generated patches and preserve warning context."""
        warnings = list(result.warnings)
        file_patches = self._valid_patches(
            patches=result.file_patches,
            allowed_files=allowed_files,
            warnings=warnings,
            incident_context=incident_context,
        )
        test_patches = self._valid_patches(
            patches=result.test_patches,
            allowed_files=allowed_files,
            warnings=warnings,
            incident_context=incident_context,
        )

        return result.model_copy(
            update={
                "file_patches": file_patches,
                "test_patches": test_patches,
                "warnings": self._unique(warnings),
                "generated_diff": bool(file_patches or test_patches),
            }
        )

    def _valid_patches(
        self,
        *,
        patches: list[FilePatch],
        allowed_files: set[str],
        warnings: list[str],
        incident_context: str,
    ) -> list[FilePatch]:
        valid_patches: list[FilePatch] = []
        for patch in patches:
            normalized_path = self._normalize_path(patch.file_path)

            if normalized_path not in allowed_files:
                warnings.append(
                    f"Rejected patch for unreadable or unapproved file: {patch.file_path}"
                )
                continue

            if not patch.unified_diff.strip():
                warnings.append(f"Rejected empty diff for file: {patch.file_path}")
                continue

            if not self._diff_mentions_file(
                unified_diff=patch.unified_diff,
                file_path=normalized_path,
            ):
                warnings.append(
                    f"Rejected diff whose headers do not match file: {patch.file_path}"
                )
                continue

            if self._contains_placeholder_implementation(patch.unified_diff):
                warnings.append(
                    f"Rejected patch for {patch.file_path} because it contains "
                    "placeholder or incomplete implementation markers."
                )
                continue

            if self._changes_public_function_signature_without_call_site(
                patch.unified_diff,
                patch_count=len(patches),
            ):
                warnings.append(
                    f"Rejected patch for {patch.file_path} because it appears to "
                    "change a public function signature without corresponding "
                    "call-site patches."
                )
                continue

            if self._is_upload_dedupe_patch_to_routing_code(
                file_path=normalized_path,
                incident_context=incident_context,
            ):
                warnings.append(
                    "Rejected patch for "
                    f"{normalized_path} because upload deduplication should not be "
                    "implemented in routing code without direct upload ownership evidence."
                )
                continue

            valid_patches.append(patch.model_copy(update={"file_path": normalized_path}))

        return valid_patches

    def _diff_mentions_file(self, *, unified_diff: str, file_path: str) -> bool:
        normalized_diff = unified_diff.replace("\\", "/")
        accepted_headers = {
            f"--- a/{file_path}",
            f"+++ b/{file_path}",
            f"--- {file_path}",
            f"+++ {file_path}",
        }
        return any(header in normalized_diff for header in accepted_headers)

    def _contains_placeholder_implementation(self, unified_diff: str) -> bool:
        if any(marker in unified_diff for marker in PLACEHOLDER_IMPLEMENTATION_MARKERS):
            return True

        return any(
            line.startswith("+") and line[1:].strip() == "pass"
            or line.startswith("+") and "..." in line
            for line in unified_diff.splitlines()
        )

    def _changes_public_function_signature_without_call_site(
        self,
        unified_diff: str,
        *,
        patch_count: int,
    ) -> bool:
        if patch_count != 1:
            return False

        removed_defs: dict[str, str] = {}
        added_defs: dict[str, str] = {}

        for line in unified_diff.splitlines():
            stripped = line[1:].strip() if line.startswith(("+", "-")) else ""
            if not stripped.startswith("def "):
                continue

            function_name = stripped.removeprefix("def ").split("(", maxsplit=1)[0]
            if not function_name or function_name.startswith("_"):
                continue

            if line.startswith("-"):
                removed_defs[function_name] = stripped
            elif line.startswith("+"):
                added_defs[function_name] = stripped

        return any(
            function_name in added_defs and added_defs[function_name] != removed_signature
            for function_name, removed_signature in removed_defs.items()
        )

    def _is_upload_dedupe_patch_to_routing_code(
        self,
        *,
        file_path: str,
        incident_context: str,
    ) -> bool:
        normalized_context = incident_context.lower()
        normalized_path = file_path.lower()

        has_upload_signal = any(term in normalized_context for term in UPLOAD_DEDUPE_TERMS)
        is_routing_path = any(term in normalized_path for term in ROUTING_PATH_TERMS)
        has_upload_ownership_path = any(
            term in normalized_path for term in UPLOAD_OWNERSHIP_TERMS
        )

        return has_upload_signal and is_routing_path and not has_upload_ownership_path

    def _normalize_path(self, file_path: str) -> str:
        return file_path.replace("\\", "/").strip().removeprefix("./")

    def _unique(self, values: list[str]) -> list[str]:
        unique_values: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_values.append(normalized)
        return unique_values
