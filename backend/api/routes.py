import logging

from fastapi import APIRouter, HTTPException

from backend.config import settings
from backend.models.schemas import JobStatusResponse, VideoJobResponse, VideoRequest
from backend.services import nova_reel_service
from backend.services.nova_reel_service import JobNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/generate-video", response_model=VideoJobResponse)
def generate_video(payload: VideoRequest):
    prompt = (payload.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    if len(prompt) > settings.prompt_char_limit:
        raise HTTPException(
            status_code=400,
            detail=f"Prompt too long. Maximum {settings.prompt_char_limit} characters (~500 tokens).",
        )

    job = nova_reel_service.start_video_job(prompt)
    return VideoJobResponse(**job)


@router.get("/video-status/{job_id}", response_model=JobStatusResponse)
def get_video_status(job_id: str):
    try:
        job_status = nova_reel_service.get_job_status(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return JobStatusResponse(**job_status)


@router.get("/health")
def health_check():
    return {"status": "ok"}
