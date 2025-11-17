import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from backend.config import settings

logger = logging.getLogger(__name__)

_assumed_credentials: Optional[dict] = None
_credentials_expiration: Optional[datetime] = None

_base_session = boto3.Session(
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    aws_session_token=settings.aws_session_token,
    region_name=settings.aws_region,
)


class BedrockClientError(RuntimeError):
    """Raised when AWS client creation fails."""


def _assume_role_if_needed() -> dict:
    global _assumed_credentials, _credentials_expiration
    if _assumed_credentials and _credentials_expiration:
        if datetime.now(timezone.utc) + timedelta(minutes=5) < _credentials_expiration:
            return _assumed_credentials

    sts_client = _base_session.client("sts", config=BotoConfig(retries={"max_attempts": 3}))
    try:
        response = sts_client.assume_role(
            RoleArn=settings.bedrock_role_arn,
            RoleSessionName="nova-reel-local-app",
            DurationSeconds=3600,
        )
    except (ClientError, BotoCoreError) as exc:
        logger.exception("Unable to assume IAM role for Bedrock access")
        raise BedrockClientError("Failed to assume IAM role. Check your credentials and permissions.") from exc

    credentials = response["Credentials"]
    _assumed_credentials = {
        "aws_access_key_id": credentials["AccessKeyId"],
        "aws_secret_access_key": credentials["SecretAccessKey"],
        "aws_session_token": credentials["SessionToken"],
    }
    _credentials_expiration = credentials["Expiration"].astimezone(timezone.utc)
    return _assumed_credentials


def _create_client(service_name: str):
    creds = _assume_role_if_needed()
    try:
        client = boto3.client(
            service_name,
            region_name=settings.aws_region,
            aws_access_key_id=creds["aws_access_key_id"],
            aws_secret_access_key=creds["aws_secret_access_key"],
            aws_session_token=creds["aws_session_token"],
            config=BotoConfig(retries={"max_attempts": 5, "mode": "adaptive"}),
        )
    except (ClientError, BotoCoreError) as exc:
        logger.exception("Failed to create %s client", service_name)
        raise BedrockClientError(f"Unable to create {service_name} client.") from exc
    return client


_bedrock_client = None
_s3_client = None


def get_bedrock_runtime_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = _create_client("bedrock-runtime")
    return _bedrock_client


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = _create_client("s3")
    return _s3_client
