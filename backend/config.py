import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseSettings, Field, validator

load_dotenv()


class Settings(BaseSettings):
    aws_access_key_id: str = Field(..., env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(..., env="AWS_SECRET_ACCESS_KEY")
    aws_session_token: Optional[str] = Field(default=None, env="AWS_SESSION_TOKEN")
    aws_region: str = Field("us-east-1", env="AWS_REGION")

    bedrock_role_arn: str = Field(..., env="BEDROCK_ROLE_ARN")
    bedrock_model_id: str = Field("amazon.nova-reel-v1:0", env="BEDROCK_NOVA_REEL_MODEL_ID")
    bedrock_s3_bucket: str = Field(..., env="BEDROCK_S3_BUCKET")
    bedrock_s3_prefix: str = Field("bedrock-temp", env="BEDROCK_S3_PREFIX")

    output_local_dir: str = Field("videos", env="OUTPUT_LOCAL_DIR")

    app_host: str = Field("127.0.0.1", env="APP_HOST")
    app_port: int = Field(8000, env="APP_PORT")

    prompt_char_limit: int = Field(2400, env="PROMPT_CHAR_LIMIT")

    class Config:
        env_file = ".env"
        case_sensitive = False

    @validator("bedrock_s3_prefix", pre=True)
    def normalize_prefix(cls, value: str) -> str:
        value = value or ""
        return value.strip("/")

    @validator("output_local_dir", pre=True)
    def ensure_local_dir(cls, value: str) -> str:
        value = value or "videos"
        Path(value).mkdir(parents=True, exist_ok=True)
        return value


@lru_cache()
def get_settings() -> Settings:
    try:
        return Settings()
    except Exception as exc:
        raise RuntimeError("Failed to load application settings. Ensure your .env file is configured.") from exc


settings = get_settings()
