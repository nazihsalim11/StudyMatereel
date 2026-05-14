import logging
import os
import shutil
import uuid
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from video_logic import process_file

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="StudyReels API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("temporary_storage/videos", exist_ok=True)
os.makedirs("temporary_storage/uploads", exist_ok=True)

# Serve rendered videos and raw slide/audio assets
app.mount("/videos", StaticFiles(directory="temporary_storage/videos"), name="videos")
app.mount("/assets", StaticFiles(directory="temporary_storage"), name="assets")

# In-memory job store — swap for Redis in production
jobs: dict[str, dict] = {}

ALLOWED_EXTENSIONS = {".pdf", ".pptx"}


class JobStatus(BaseModel):
    job_id: str
    status: str  # "pending" | "processing" | "completed" | "failed"
    progress: int = 0
    video_url: Optional[str] = None
    error: Optional[str] = None


@app.get("/")
async def root():
    return {"message": "StudyReels API is running", "version": "1.0.0"}


@app.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    job_id = str(uuid.uuid4())
    file_path = f"temporary_storage/uploads/{job_id}{ext}"

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "video_url": None,
        "error": None,
    }

    background_tasks.add_task(process_file, job_id, file_path, jobs)
    logger.info("Job %s queued — file: %s", job_id, file.filename)

    return {"job_id": job_id}


@app.get("/status/{job_id}", response_model=JobStatus)
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@app.get("/jobs")
async def list_jobs():
    return list(jobs.values())


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    temp_dir = f"temporary_storage/{job_id}"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    del jobs[job_id]
    return {"message": f"Job {job_id} deleted"}
