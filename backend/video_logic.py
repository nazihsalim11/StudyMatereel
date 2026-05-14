"""
Core pipeline: PDF/PPTX → slide images → Groq scripts → ElevenLabs audio
              → word-level subtitles → Remotion video render.
"""
import base64
import json
import logging
import os
import platform
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from pdf2image import convert_from_path
from PIL import Image

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# ── Windows tool paths ─────────────────────────────────────────────
IS_WINDOWS = platform.system() == "Windows"

POPPLER_PATH: str | None = os.getenv("POPPLER_PATH") or (
    r"C:\poppler\Library\bin" if IS_WINDOWS else None
)

LIBREOFFICE_PATH: str = os.getenv("LIBREOFFICE_PATH") or (
    r"C:\Program Files\LibreOffice\program\soffice.exe" if IS_WINDOWS else "libreoffice"
)


# ── Job state helper ─────────────────────────────────────────────

def _update(jobs: dict, job_id: str, **kwargs) -> None:
    jobs[job_id].update(kwargs)


# ── Main pipeline ─────────────────────────────────────────────

def process_file(job_id: str, file_path: str, jobs: dict) -> None:
    """Entry point called by FastAPI BackgroundTasks."""
    try:
        _update(jobs, job_id, status="processing", progress=5)
        temp_dir = f"temporary_storage/{job_id}"
        os.makedirs(temp_dir, exist_ok=True)

        ext = Path(file_path).suffix.lower()

        logger.info("[%s] Converting slides to images…", job_id)
        image_paths = _convert_to_images(file_path, temp_dir, ext)
        if not image_paths:
            raise ValueError("No slides found in the uploaded file.")
        _update(jobs, job_id, progress=25)

        logger.info("[%s] Generating scripts with Groq…", job_id)
        scripts = _generate_scripts(image_paths)
        _update(jobs, job_id, progress=45)

        logger.info("[%s] Synthesising audio with ElevenLabs…", job_id)
        audio_paths = _generate_audio(scripts, temp_dir)
        _update(jobs, job_id, progress=65)

        logger.info("[%s] Building subtitles…", job_id)
        subtitle_data = _build_subtitles(scripts, audio_paths)
        subtitle_path = os.path.join(temp_dir, "subtitles.json")
        with open(subtitle_path, "w", encoding="utf-8") as f:
            json.dump(subtitle_data, f, indent=2, ensure_ascii=False)
        _update(jobs, job_id, progress=75)

        logger.info("[%s] Rendering video…", job_id)
        _render_video(job_id, image_paths, audio_paths, subtitle_data, temp_dir)
        _update(jobs, job_id, status="completed", progress=100, video_url=f"/videos/{job_id}.mp4")
        logger.info("[%s] Pipeline complete.", job_id)

    except Exception:
        logger.exception("[%s] Pipeline failed.", job_id)
        import traceback
        _update(jobs, job_id, status="failed", error=traceback.format_exc(limit=3))


# ── Step 1: slide conversion ────────────────────────────────────────────

def _convert_to_images(file_path: str, output_dir: str, ext: str) -> list[str]:
    slides_dir = os.path.join(output_dir, "slides")
    os.makedirs(slides_dir, exist_ok=True)

    if ext == ".pdf":
        pages = convert_from_path(file_path, dpi=150, fmt="png", poppler_path=POPPLER_PATH)
        paths = []
        for i, page in enumerate(pages):
            out = os.path.join(slides_dir, f"slide_{i:03d}.png")
            page.save(out, "PNG")
            paths.append(out)
        return paths

    if ext == ".pptx":
        if IS_WINDOWS and not Path(LIBREOFFICE_PATH).exists():
            raise RuntimeError(
                f"LibreOffice not found at '{LIBREOFFICE_PATH}'. "
                "Install from https://www.libreoffice.org or set LIBREOFFICE_PATH in .env"
            )
        result = subprocess.run(
            [LIBREOFFICE_PATH, "--headless", "--convert-to", "pdf",
             "--outdir", os.path.dirname(file_path), file_path],
            capture_output=True, timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"LibreOffice conversion failed: {result.stderr.decode()}")
        return _convert_to_images(file_path.replace(".pptx", ".pdf"), output_dir, ".pdf")

    raise ValueError(f"Unsupported extension: {ext}")


# ── Step 2: script generation (Groq vision) ────────────────────────────────

def _generate_scripts(image_paths: list[str]) -> list[str]:
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set — using placeholder scripts.")
        return [f"This is slide {i + 1}." for i in range(len(image_paths))]

    try:
        from groq import Groq

        client = Groq(api_key=GROQ_API_KEY)
        prompt = (
            "You are a concise educational narrator. "
            "Analyse this slide and write a clear, engaging 2-3 sentence narration "
            "suitable for a 30-second vertical video reel. "
            "Focus on the key concept. Do not say 'slide'."
        )

        scripts = []
        for path in image_paths:
            with open(path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")

            response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                max_tokens=300,
            )
            scripts.append(response.choices[0].message.content.strip())
        return scripts

    except Exception:
        logger.exception("Groq call failed — falling back to placeholders.")
        return [f"Slide {i + 1}." for i in range(len(image_paths))]


# ── Step 3: audio synthesis ────────────────────────────────────────────

def _generate_audio(scripts: list[str], output_dir: str) -> list[str]:
    audio_dir = os.path.join(output_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    if not ELEVENLABS_API_KEY:
        logger.warning("ELEVENLABS_API_KEY not set — generating silent audio stubs.")
        return [_silent_stub(os.path.join(audio_dir, f"audio_{i:03d}.mp3"), 4) for i in range(len(scripts))]

    try:
        from elevenlabs.client import ElevenLabs

        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        paths = []
        for i, script in enumerate(scripts):
            audio_generator = client.generate(
                text=script, voice=ELEVENLABS_VOICE_ID, model="eleven_multilingual_v2",
            )
            path = os.path.join(audio_dir, f"audio_{i:03d}.mp3")
            with open(path, "wb") as f:
                for chunk in audio_generator:
                    f.write(chunk)
            paths.append(path)
        return paths

    except Exception:
        logger.exception("ElevenLabs call failed — generating silent stubs.")
        return [_silent_stub(os.path.join(audio_dir, f"audio_{i:03d}.mp3"), 4) for i in range(len(scripts))]


def _silent_stub(path: str, duration_s: int = 4) -> str:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(duration_s), path],
        check=True, capture_output=True,
    )
    return path


# ── Step 4: subtitle generation ────────────────────────────────────────────

def _build_subtitles(scripts: list[str], audio_paths: list[str]) -> list[dict]:
    result = []
    for i, (script, audio_path) in enumerate(zip(scripts, audio_paths)):
        duration = _audio_duration(audio_path)
        words = script.split()
        if not words:
            continue
        time_per_word = duration / len(words)
        result.append({
            "slide": i,
            "duration": duration,
            "words": [
                {"word": w, "start": round(j * time_per_word, 3), "end": round((j + 1) * time_per_word, 3)}
                for j, w in enumerate(words)
            ],
        })
    return result


def _audio_duration(audio_path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return 4.0


# ── Step 5: Remotion render ─────────────────────────────────────────────

def _render_video(job_id, image_paths, audio_paths, subtitle_data, temp_dir):
    videos_dir = "temporary_storage/videos"
    os.makedirs(videos_dir, exist_ok=True)
    output_path = os.path.join(videos_dir, f"{job_id}.mp4")

    props = {
        "slides": [
            {
                "imageUrl": f"{BACKEND_URL}/assets/{job_id}/slides/slide_{i:03d}.png",
                "audioUrl": f"{BACKEND_URL}/assets/{job_id}/audio/audio_{i:03d}.mp3",
                "duration": subtitle_data[i]["duration"] if i < len(subtitle_data) else 4.0,
            }
            for i in range(len(image_paths))
        ],
        "subtitles": subtitle_data,
    }

    props_path = os.path.join(temp_dir, "props.json")
    with open(props_path, "w") as f:
        json.dump(props, f)

    remotion_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "remotion"))

    try:
        subprocess.run(
            ["npx", "remotion", "render", "StudyReel", output_path, "--props", props_path],
            cwd=remotion_dir, check=True, timeout=600,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.warning("Remotion unavailable — using ffmpeg fallback renderer.")
        _ffmpeg_fallback(image_paths, audio_paths, output_path)

    return output_path


def _ffmpeg_fallback(image_paths, audio_paths, output_path):
    segment_dir = os.path.dirname(output_path)
    segments = []

    for i, (img, aud) in enumerate(zip(image_paths, audio_paths)):
        seg = os.path.join(segment_dir, f"_seg_{i:03d}.mp4")
        duration = _audio_duration(aud)
        subprocess.run(
            [
                "ffmpeg", "-y", "-loop", "1", "-i", img, "-i", aud,
                "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "192k",
                "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black",
                "-shortest", "-t", str(duration), seg,
            ],
            check=True, capture_output=True,
        )
        segments.append(seg)

    concat_list = os.path.join(segment_dir, "_concat.txt")
    with open(concat_list, "w") as f:
        for seg in segments:
            f.write(f"file '{os.path.abspath(seg)}'\n")

    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", output_path],
        check=True, capture_output=True,
    )

    for seg in segments:
        os.remove(seg)
    os.remove(concat_list)
