import logging
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from botocore.exceptions import BotoCoreError, ClientError

from backend.config import settings
from backend.services.bedrock_client import get_bedrock_runtime_client, get_s3_client

logger = logging.getLogger(__name__)


class JobNotFoundError(RuntimeError):
    pass


@dataclass
class VideoJob:
    job_id: str
    invocation_arn: str
    status: str = "pending"
    detail: Optional[str] = None
    video_url: Optional[str] = None
    local_path: Optional[str] = None
    s3_prefix: str = field(default="")


_JOB_STORE: Dict[str, VideoJob] = {}


def start_video_job(prompt: str) -> Dict[str, str]:
    bedrock_client = get_bedrock_runtime_client()
    job_id = str(uuid.uuid4())
    seed = random.randint(0, 2 ** 31 - 1)
    s3_prefix = f"{settings.bedrock_s3_prefix}/{job_id}"

    model_input = {
        "taskType": "TEXT_VIDEO",
        "textToVideoParams": {"text": prompt},
        "videoGenerationConfig": {
            "fps": 24,
            "durationSeconds": 6,
            "dimension": "1280x720",
            "seed": seed,
        },
    }

    request = {
        "modelId": settings.bedrock_model_id,
        "modelInput": model_input,
        "outputDataConfig": {
            "s3Location": {
                "bucketName": settings.bedrock_s3_bucket,
                "prefix": s3_prefix,
            }
        },
    }

    try:
        response = bedrock_client.start_async_invoke(**request)
    except (ClientError, BotoCoreError) as exc:
        logger.exception("Failed to start Nova Reel video generation job")
        raise RuntimeError("Unable to start video generation job. Check Bedrock access and quotas.") from exc

    invocation_arn = response.get("invocationArn")
    if not invocation_arn:
        raise RuntimeError("Bedrock did not return an invocation ARN.")

    job = VideoJob(job_id=job_id, invocation_arn=invocation_arn, status="pending", s3_prefix=s3_prefix)
    _JOB_STORE[job_id] = job
    logger.info("Started Nova Reel job %s", job_id)
    return {"job_id": job_id, "status": job.status}


def get_job_status(job_id: str) -> Dict[str, Optional[str]]:
    job = _JOB_STORE.get(job_id)
    if not job:
        raise JobNotFoundError(f"Job {job_id} not found")

    if job.status in {"completed", "failed"}:
        return _serialize_job(job)

    bedrock_client = get_bedrock_runtime_client()
    try:
        response = bedrock_client.get_async_invoke(invocationArn=job.invocation_arn)
    except (ClientError, BotoCoreError) as exc:
        logger.exception("Failed to fetch job status for %s", job_id)
        raise RuntimeError("Unable to retrieve job status from Bedrock.") from exc

    status = (response.get("status") or "").lower()
    if status in {"starting", "in_progress", "inprogress"}:
        job.status = "in_progress"
    elif status == "completed":
        _handle_job_completion(job)
    elif status == "failed":
        failure_message = response.get("failureMessage") or "Video generation failed."
        job.status = "failed"
        job.detail = failure_message
        logger.error("Nova Reel job %s failed: %s", job_id, failure_message)
    else:
        job.status = "pending"

    return _serialize_job(job)


def _handle_job_completion(job: VideoJob) -> None:
    bucket, prefix = _determine_s3_location(job)
    local_filename = f"{job.job_id}.mp4"
    local_path = Path(settings.output_local_dir) / local_filename
    downloaded = _download_video_from_s3(bucket, prefix, local_path)
    if not downloaded:
        job.status = "failed"
        job.detail = "Video file was not found in the S3 output."
        return

    job.status = "completed"
    job.local_path = str(local_path)
    job.video_url = f"/videos/{local_filename}"
    job.detail = "Video generation completed."
    logger.info("Video for job %s stored at %s", job.job_id, job.local_path)


def _determine_s3_location(job: VideoJob):
    bucket = settings.bedrock_s3_bucket
    prefix = job.s3_prefix or settings.bedrock_s3_prefix
    return bucket, prefix


def _download_video_from_s3(bucket: str, prefix: str, local_path: Path) -> bool:
    s3_client = get_s3_client()
    try:
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    except (ClientError, BotoCoreError) as exc:
        logger.exception("Unable to list S3 objects for %s/%s", bucket, prefix)
        return False

    contents = response.get("Contents") or []
    video_key = None
    for obj in contents:
        key = obj.get("Key", "")
        if key.lower().endswith(".mp4"):
            video_key = key
            break
    if not video_key:
        return False

    local_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        s3_client.download_file(bucket, video_key, str(local_path))
    except (ClientError, BotoCoreError) as exc:
        logger.exception("Failed to download video from S3: %s", video_key)
        return False

    _cleanup_s3_objects(bucket, prefix, contents)
    return True


def _cleanup_s3_objects(bucket: str, prefix: str, objects: list) -> None:
    if not objects:
        return
    s3_client = get_s3_client()
    object_ids = [{"Key": obj["Key"]} for obj in objects if obj.get("Key")]
    if not object_ids:
        return
    try:
        s3_client.delete_objects(Bucket=bucket, Delete={"Objects": object_ids, "Quiet": True})
    except (ClientError, BotoCoreError):
        logger.warning("Failed to delete temporary S3 objects for prefix %s", prefix)


def _serialize_job(job: VideoJob) -> Dict[str, Optional[str]]:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "detail": job.detail,
        "video_url": job.video_url,
    }
