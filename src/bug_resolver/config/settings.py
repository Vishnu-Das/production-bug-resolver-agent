"""Application settings loaded from environment variables and local defaults."""

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application-level settings.

    All external configuration should come through this class instead of being
    hardcoded inside agents, providers, or workflows.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Production Bug Resolver Agent"
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str | None = Field(default=None, alias="LOG_LEVEL")
    runtime_logs_dir: Path = Field(default=Path("logs"), alias="RUNTIME_LOGS_DIR")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    langsmith_tracing: bool = Field(
        default=False,
        validation_alias=AliasChoices("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"),
    )
    langsmith_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LANGSMITH_API_KEY", "LANGCHAIN_API_KEY"),
    )
    langsmith_project: str = Field(
        default="production-bug-resolver-agent",
        alias="LANGSMITH_PROJECT",
    )
    langsmith_endpoint: str = Field(default="", alias="LANGSMITH_ENDPOINT")

    target_repo_path: Path = Field(default=Path("sample_data/target_repos/conversational_rag"))
    incidents_dir: Path = Field(default=Path("sample_data/incidents"))
    logs_dir: Path = Field(default=Path("sample_data/logs"))
    reports_dir: Path = Field(default=Path("reports"))
    historical_rca_dir: Path = Field(default=Path("reports"), alias="HISTORICAL_RCA_DIR")
    faiss_index_dir: Path = Field(default=Path("storage/faiss"))
    knowledge_base_dir: Path = Field(default=Path("sample_data/knowledge_base"))

    max_retries: int = Field(default=2, alias="MAX_RETRIES")
    max_investigation_steps: int = Field(
        default=16,
        ge=1,
        alias="MAX_INVESTIGATION_STEPS",
    )
    confidence_threshold: float = Field(default=0.75, alias="CONFIDENCE_THRESHOLD")


def get_settings() -> AppSettings:
    """Load application settings from environment variables."""
    return AppSettings()
