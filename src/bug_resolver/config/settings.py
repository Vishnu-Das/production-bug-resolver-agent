"""Application settings loaded from environment variables and local defaults."""

from pathlib import Path

from pydantic import Field
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

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")

    target_repo_path: Path = Field(default=Path("sample_data/target_repos/conversational_rag"))
    incidents_dir: Path = Field(default=Path("sample_data/incidents"))
    logs_dir: Path = Field(default=Path("sample_data/logs"))
    reports_dir: Path = Field(default=Path("reports"))
    faiss_index_dir: Path = Field(default=Path("storage/faiss"))
    knowledge_base_dir: Path = Field(default=Path("sample_data/knowledge_base"))

    max_retries: int = Field(default=2, alias="MAX_RETRIES")
    confidence_threshold: float = Field(default=0.75, alias="CONFIDENCE_THRESHOLD")


def get_settings() -> AppSettings:
    """Load application settings from environment variables."""
    return AppSettings()
