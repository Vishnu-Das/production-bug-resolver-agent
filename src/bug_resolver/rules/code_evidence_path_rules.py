"""Generic path-role scoring rules for primary code evidence selection."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from bug_resolver.signals.code_path_signals import (
    DEFAULT_SUPPORT_PATH_ROLES,
    CodePathRole,
)


class CodeEvidencePathRules:
    """Score whether a code path should be treated as primary implementation evidence."""

    def __init__(self, support_roles: tuple[CodePathRole, ...] = DEFAULT_SUPPORT_PATH_ROLES) -> None:
        self.support_roles = support_roles

    def support_adjustment(
        self,
        path: str,
        signals: set[str],
        *,
        penalty: float,
        mention_bonus: float,
    ) -> float:
        """Return a score adjustment for support paths based on query/incident signals."""
        adjustment = 0.0

        for role in self.roles_for_path(path):
            if signals & role.query_terms:
                adjustment += mention_bonus
            else:
                adjustment += penalty

        return adjustment

    def is_support_path(self, path: str) -> bool:
        """Return whether a path usually represents secondary/supporting code."""
        return bool(self.roles_for_path(path))

    def is_allowed_support_path(self, path: str, signals: set[str]) -> bool:
        """Return whether support path roles are explicitly requested by signals."""
        roles = self.roles_for_path(path)
        if not roles:
            return True

        return all(signals & role.query_terms for role in roles)

    def roles_for_path(self, path: str) -> list[CodePathRole]:
        """Return support roles matched by a normalized path."""
        path_tokens = self.tokens(path)
        path_name = PurePosixPath(path.replace("\\", "/").lower()).name
        roles = [role for role in self.support_roles if path_tokens & role.path_terms]

        if path_name.startswith("test_") or path_name.endswith("_test.py"):
            test_role = self._role_by_name("test")
            if test_role and test_role not in roles:
                roles.append(test_role)

        if path_name.endswith(".ipynb"):
            notebook_role = self._role_by_name("notebook")
            if notebook_role and notebook_role not in roles:
                roles.append(notebook_role)

        return roles

    def tokens(self, value: str) -> set[str]:
        """Split path or query text into lowercase tokens, including snake_case parts."""
        tokens = set(re.findall(r"[a-z0-9_]+", value.lower()))
        split_tokens = {
            part
            for token in tokens
            for part in token.split("_")
            if part
        }
        return tokens | split_tokens

    def _role_by_name(self, name: str) -> CodePathRole | None:
        for role in self.support_roles:
            if role.name == name:
                return role
        return None
