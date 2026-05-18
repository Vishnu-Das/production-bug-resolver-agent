from bug_resolver.retrieval.code_file_loader import CodeFileLoader


def test_code_file_loader_loads_supported_files(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    python_file = repo_dir / "app.py"
    python_file.write_text("print('hello')", encoding="utf-8")

    readme_file = repo_dir / "README.md"
    readme_file.write_text("# Project", encoding="utf-8")

    provider_file = repo_dir / "data.csv"
    provider_file.write_text("a,b,c", encoding="utf-8")

    loader = CodeFileLoader(repo_path=repo_dir)

    files = loader.load_files()

    relative_paths = {file.relative_path for file in files}

    assert "app.py" in relative_paths
    assert "README.md" in relative_paths
    assert "data.csv" not in relative_paths


def test_code_file_loader_returns_empty_list_for_missing_repo(tmp_path):
    loader = CodeFileLoader(repo_path=tmp_path / "missing")

    files = loader.load_files()

    assert files == []


def test_code_file_loader_skips_empty_files(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    empty_file = repo_dir / "empty.py"
    empty_file.write_text("   ", encoding="utf-8")

    loader = CodeFileLoader(repo_path=repo_dir)

    files = loader.load_files()

    assert files == []


def test_code_file_loader_skips_ignored_directories(tmp_path):
    repo_dir = tmp_path / "repo"
    venv_dir = repo_dir / ".venv"
    venv_dir.mkdir(parents=True)

    ignored_file = venv_dir / "ignored.py"
    ignored_file.write_text("print('ignored')", encoding="utf-8")

    valid_file = repo_dir / "valid.py"
    valid_file.write_text("print('valid')", encoding="utf-8")

    loader = CodeFileLoader(repo_path=repo_dir)

    files = loader.load_files()

    relative_paths = {file.relative_path for file in files}

    assert "valid.py" in relative_paths
    assert ".venv/ignored.py" not in relative_paths