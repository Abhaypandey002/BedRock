from typing import Optional

from pydantic import BaseModel, Field


class VideoRequest(BaseModel):
    prompt: str = Field(..., description="Text prompt for Nova Reel")


class VideoJobResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    detail: Optional[str] = None
    video_url: Optional[str] = None
