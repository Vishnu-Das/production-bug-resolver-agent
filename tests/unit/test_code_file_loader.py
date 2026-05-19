from pathlib import Path

from bug_resolver.retrieval.code_file_loader import CodeFileLoader


def test_code_file_loader_excludes_markdown_files(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    python_file = repo_path / "app.py"
    python_file.write_text("print('hello')\n", encoding="utf-8")

    readme_file = repo_path / "README.md"
    readme_file.write_text("# Project docs\n", encoding="utf-8")

    loader = CodeFileLoader(repo_path)

    loaded_files = loader.load_files()
    relative_paths = {loaded_file.relative_path for loaded_file in loaded_files}

    assert "app.py" in relative_paths
    assert "README.md" not in relative_paths


def test_code_file_loader_allows_supported_config_files(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    pyproject_file = repo_path / "pyproject.toml"
    pyproject_file.write_text("[project]\nname = 'demo'\n", encoding="utf-8")

    yaml_file = repo_path / "config.yaml"
    yaml_file.write_text("app: demo\n", encoding="utf-8")

    json_file = repo_path / "settings.json"
    json_file.write_text('{"app": "demo"}\n', encoding="utf-8")

    loader = CodeFileLoader(repo_path)

    loaded_files = loader.load_files()
    relative_paths = {loaded_file.relative_path for loaded_file in loaded_files}

    assert "pyproject.toml" in relative_paths
    assert "config.yaml" in relative_paths
    assert "settings.json" in relative_paths


def test_code_file_loader_skips_ignored_directories(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    ignored_dir = repo_path / "__pycache__"
    ignored_dir.mkdir()

    ignored_file = ignored_dir / "cached.py"
    ignored_file.write_text("print('ignore me')\n", encoding="utf-8")

    valid_file = repo_path / "main.py"
    valid_file.write_text("print('include me')\n", encoding="utf-8")

    loader = CodeFileLoader(repo_path)

    loaded_files = loader.load_files()
    relative_paths = {loaded_file.relative_path for loaded_file in loaded_files}

    assert "main.py" in relative_paths
    assert "__pycache__/cached.py" not in relative_paths