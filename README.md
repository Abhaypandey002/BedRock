# Nova Reel Local Text-to-Video App

Generate short preview videos locally using [Amazon Bedrock](https://aws.amazon.com/bedrock/) and the **Amazon Nova Reel (`amazon.nova-reel-v1:0`)** model. This project exposes a simple web UI backed by FastAPI that starts Nova Reel async jobs, downloads the resulting MP4 files to your machine, and serves them back to the browser for playback and download.

> **Local-first design:** Videos only live in your `./videos/` folder. The app touches AWS storage only because Nova Reel currently writes job output to S3. Files are automatically downloaded and the temporary S3 objects are deleted immediately afterward.

---

## Architecture Overview

```
Browser (HTML/CSS/JS)
        │
        ▼
FastAPI backend (Python)
        │  calls
        ▼
Amazon Bedrock Runtime (Nova Reel async invoke)
        │  writes temporary output
        ▼
Ephemeral S3 bucket (per Nova Reel requirements)
        │  downloaded & cleaned
        ▼
Local filesystem ./videos/<job>.mp4
```

- **Frontend:** Static HTML + vanilla JS served by FastAPI.
- **Backend:** FastAPI + boto3. Manages Nova Reel async jobs, polling, local downloads, and video serving.
- **Storage:** Local `videos/` directory (gitignored). Temporary S3 bucket is used only as a transport layer for Nova Reel output.

---

## Prerequisites

1. **Python 3.10+**
2. **AWS account** with Bedrock enabled in your chosen region.
3. **Nova Reel access** in Amazon Bedrock.
4. **IAM role** that FastAPI can assume with permissions:
   - `sts:AssumeRole` (from your base credentials)
   - `bedrock:StartAsyncInvoke`, `bedrock:GetAsyncInvoke` for the Nova Reel model
   - `s3:ListBucket`, `s3:GetObject`, `s3:DeleteObject` on the temporary bucket
5. A dedicated **S3 bucket** (e.g., `my-temp-bedrock-output`) used only for Nova Reel outputs.
6. Recommended: VS Code with the Python extension for local debugging.

---

## Setup

1. **Clone the repository**
   ```bash
   git clone <repo> nova-reel-app
   cd nova-reel-app
   ```
2. **Create the videos directory** (the app also auto-creates it):
   ```bash
   mkdir -p videos
   ```
3. **Create a `.env` file** from the provided template:
   ```bash
   cp .env.example .env
   ```
4. **Edit `.env`** with your values:
   ```env
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   AWS_SESSION_TOKEN= # optional
   AWS_REGION=us-east-1
   BEDROCK_ROLE_ARN=arn:aws:iam::123456789012:role/BedrockExecutionRole
   BEDROCK_NOVA_REEL_MODEL_ID=amazon.nova-reel-v1:0
   BEDROCK_S3_BUCKET=my-temp-bedrock-output
   BEDROCK_S3_PREFIX=bedrock-temp
   OUTPUT_LOCAL_DIR=videos
   APP_HOST=127.0.0.1
   APP_PORT=8000
   PROMPT_CHAR_LIMIT=2400
   ```
   - **Never commit `.env`.**
   - `BEDROCK_S3_BUCKET` must exist in the configured region and be accessible by the IAM role. The bucket only holds temporary Nova Reel results and is cleaned automatically.

---

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

---

## Running the App

```bash
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

- `frontend/index.html` is served at the root.
- API endpoints are under `/api/*`.
- Generated videos are exposed as `/videos/<job_id>.mp4`.

---

## Usage

1. Type a scene description in the prompt box (think storyboards, camera angles, moods).
2. Character limit is enforced at **2,400 characters (~500 tokens)** to comply with Nova Reel limits. The UI shows a live counter and the backend validates again.
3. Click **Generate Video**.
4. The backend starts an async Nova Reel job and begins polling every few seconds.
5. When complete, the MP4 file is downloaded into `./videos/<job_id>.mp4` and becomes available for playback and download in the browser.
6. Videos remain on your local disk until you delete them.

Expect each clip (6 seconds, 1280×720 at 24 fps) to take roughly 1–3 minutes depending on load.

---

## Environment & Security Notes

- Credentials are loaded via `.env` using `python-dotenv` and are **never logged**.
- The backend assumes the IAM role specified by `BEDROCK_ROLE_ARN` and uses the returned temporary credentials for Bedrock + S3.
- **S3 usage is transient**: Nova Reel writes to `s3://<bucket>/<prefix>/<job_id>/`. After download, the app attempts to delete the S3 objects so no data resides in AWS longer than necessary.
- All generated content is stored locally under `./videos/`. Keep this folder safe or add your own rotation policy.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `Failed to assume IAM role` | Wrong ARN or missing trust policy | Verify role ARN and allow your base IAM user to assume it |
| `Unable to start video generation job` | Nova Reel not enabled, wrong region, or throttling | Confirm the model is available in your region and quotas are sufficient |
| Status stuck on `pending` | Async job still running or `get_async_invoke` permissions missing | Ensure `bedrock:GetAsyncInvoke` is granted and wait longer |
| No video downloaded | Nova Reel wrote metadata but not MP4 | Check CloudWatch logs in AWS or contact support. The app will show a failure message |
| Permission denied on S3 cleanup | IAM role lacks `s3:DeleteObject` | Add delete permissions for the prefix. Cleanup is optional but recommended |

---

## Future Enhancements

- Persist job metadata in SQLite or DynamoDB for restarts and auditing.
- Support multiple durations, resolutions, and seeds through the UI.
- Add authentication + user quotas for shared deployments.
- Hook into WebSockets for push-style updates instead of polling.

---

## Repository Layout

```
backend/
  app.py                # FastAPI app + static serving
  api/routes.py         # REST endpoints
  config.py             # Settings loader
  logging_config.py     # Structured logging
  models/schemas.py     # Pydantic models
  services/
    bedrock_client.py   # STS assume role + boto3 clients
    nova_reel_service.py# Job lifecycle + S3 downloads
frontend/
  index.html            # UI shell
  styles.css            # Styling
  app.js                # Frontend logic + polling
videos/                 # Local storage for generated MP4s (gitignored)
```

---

## Cleaning Up

Videos accumulate over time. Delete files inside `videos/` manually or schedule a cron job if disk space is a concern. Because the data is local-first, removing files locally is sufficient.
