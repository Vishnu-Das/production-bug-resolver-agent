"""Tests for local patch context file reads."""

from __future__ import annotations

import pytest

from bug_resolver.providers.patches import LocalFilePatchContextProvider


@pytest.mark.asyncio
async def test_local_file_patch_context_provider_reads_existing_file(tmp_path) -> None:
    target_repo = tmp_path / "repo"
    source_file = target_repo / "src" / "app.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("print('hello')\n", encoding="utf-8")

    provider = LocalFilePatchContextProvider(target_repo)

    assert await provider.read_file("src/app.py") == "print('hello')\n"


@pytest.mark.asyncio
async def test_local_file_patch_context_provider_returns_none_for_missing_file(
    tmp_path,
) -> None:
    provider = LocalFilePatchContextProvider(tmp_path / "repo")

    assert await provider.read_file("src/missing.py") is None


@pytest.mark.asyncio
async def test_local_file_patch_context_provider_blocks_path_traversal(tmp_path) -> None:
    target_repo = tmp_path / "repo"
    target_repo.mkdir()
    secret_file = tmp_path / "secret.py"
    secret_file.write_text("SECRET = True\n", encoding="utf-8")

    provider = LocalFilePatchContextProvider(target_repo)

    assert await provider.read_file("../secret.py") is None


@pytest.mark.asyncio
async def test_local_file_patch_context_provider_returns_none_for_directories(
    tmp_path,
) -> None:
    target_repo = tmp_path / "repo"
    (target_repo / "src").mkdir(parents=True)

    provider = LocalFilePatchContextProvider(target_repo)

    assert await provider.read_file("src") is None


@pytest.mark.asyncio
async def test_local_file_patch_context_provider_normalizes_windows_paths(tmp_path) -> None:
    target_repo = tmp_path / "repo"
    source_file = target_repo / "src" / "app.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("VALUE = 1\n", encoding="utf-8")

    provider = LocalFilePatchContextProvider(target_repo)

    assert await provider.read_file("src\\app.py") == "VALUE = 1\n"
