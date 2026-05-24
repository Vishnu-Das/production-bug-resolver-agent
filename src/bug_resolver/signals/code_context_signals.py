"""Query and path signals used to rank retrieved code contexts."""

TEST_QUERY_TERMS = {
    "test",
    "tests",
    "pytest",
    "unittest",
    "regression",
    "assert",
}

CONFIG_QUERY_TERMS = {
    "config",
    "configuration",
    "settings",
    "env",
    "environment",
    "json",
    "yaml",
    "yml",
    "toml",
    "docker",
    "compose",
}

INIT_QUERY_TERMS = {
    "init",
    "__init__",
    "package",
    "export",
    "exports",
}

SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".cs",
}

CONFIG_EXTENSIONS = {
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".md",
}

CONFIG_FILE_NAMES = {
    "dockerfile",
    ".env",
    ".env.example",
    "docker-compose.yml",
    "requirements.txt",
    "pyproject.toml",
    "readme.md",
}

CONFIG_DIRECTORY_MARKERS = ("/config/", "/configs/", "/settings/", "/docs/")

