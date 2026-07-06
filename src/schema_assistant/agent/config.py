from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    project_id: str = Field(default="", alias="GOOGLE_CLOUD_PROJECT")
    location: str = Field(default="europe-west8", alias="GOOGLE_CLOUD_LOCATION")
    firestore_database: str = Field(default="(default)", alias="FIRESTORE_DATABASE")
    bucket_name: str = Field(default="", alias="SCHEMA_ASSISTANT_BUCKET")

    chat_model: str = Field(default="gemini-2.5-flash", alias="CHAT_MODEL")
    embedding_model: str = Field(default="gemini-embedding-001", alias="EMBEDDING_MODEL")
    llm_enabled: bool = Field(default=True, alias="LLM_ENABLED")
    rag_enabled: bool = Field(default=False, alias="RAG_ENABLED")

    max_input_chars: int = Field(default=4000, alias="MAX_INPUT_CHARS")
    max_history_messages: int = Field(default=12, alias="MAX_HISTORY_MESSAGES")
    max_history_message_chars: int = Field(default=2000, alias="MAX_HISTORY_MESSAGE_CHARS")
    max_output_tokens: int = Field(default=2048, alias="MAX_OUTPUT_TOKENS")
    thinking_budget: int = Field(default=512, alias="THINKING_BUDGET")
    request_timeout_seconds: float = Field(default=30.0, alias="REQUEST_TIMEOUT_SECONDS")

    cost_status: Literal["green", "yellow", "red", "blocked"] = Field(
        default="green",
        alias="COST_STATUS",
    )

    @field_validator("max_input_chars", "max_history_messages", "max_output_tokens")
    @classmethod
    def _positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be positive")
        return value

    @field_validator("thinking_budget")
    @classmethod
    def _non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("value cannot be negative")
        return value


@lru_cache(maxsize=1)
def get_settings() -> AgentSettings:
    return AgentSettings()
