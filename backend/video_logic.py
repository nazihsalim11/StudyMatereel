"""
Core pipeline: PDF/PPTX → slide images → Groq scripts → edge-tts audio
              → word-level subtitles → ffmpeg video render.
"""
import json
import logging
import os
import platform
import subprocess
import textwrap
from pathlib import Path

import base64

from dotenv import load_dotenv
from pdf2image import convert_from_path

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

IS_WINDOWS = platform.system() == "Windows"

POPPLER_PATH: str | None = os.getenv("POPPLER_PATH") or (
    r"C:\poppler\Library\bin" if IS_WINDOWS else None
)

LIBREOFFICE_PATH: str = os.getenv("LIBREOFFICE_PATH") or (
    r"C:\Program Files\LibreOffice\program\soffice.exe" if IS_WINDOWS else "libreoffice"
)


# ── Job state helper ──────────────────────────────────────────────────────────

def _update(jobs: dict, job_id: str, **kwargs) -> None:
    jobs[job_id].update(kwargs)


# ── Main pipeline ─────────────────────────────────────────────────────────────

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

        logger.info("[%s] Synthesising audio…", job_id)
        audio_paths = _generate_audio(scripts, temp_dir)
        _update(jobs, job_id, progress=65)

        logger.info("[%s] Building subtitles…", job_id)
        subtitle_data = _build_subtitles(scripts, audio_paths)
        with open(os.path.join(temp_dir, "subtitles.json"), "w", encoding="utf-8") as f:
            json.dump(subtitle_data, f, indent=2, ensure_ascii=False)
        _update(jobs, job_id, progress=75)

        logger.info("[%s] Rendering video…", job_id)
        _render_video(job_id, image_paths, audio_paths, subtitle_data, temp_dir, jobs, scripts)
        _update(jobs, job_id, status="completed", progress=100, video_url=f"/videos/{job_id}.mp4")
        logger.info("[%s] Pipeline complete.", job_id)

    except Exception:
        logger.exception("[%s] Pipeline failed.", job_id)
        import traceback
        _update(jobs, job_id, status="failed", error=traceback.format_exc(limit=3))


# ── Step 1: slide conversion ──────────────────────────────────────────────────

MAX_SLIDES = 20


def _convert_to_images(file_path: str, output_dir: str, ext: str) -> list[str]:
    slides_dir = os.path.join(output_dir, "slides")
    os.makedirs(slides_dir, exist_ok=True)

    if ext == ".pdf":
        paths = []
        for i in range(1, MAX_SLIDES + 1):
            pages = convert_from_path(
                file_path, dpi=150, fmt="png",
                poppler_path=POPPLER_PATH,
                first_page=i, last_page=i,
            )
            if not pages:
                break
            out = os.path.join(slides_dir, f"slide_{i - 1:03d}.png")
            pages[0].save(out, "PNG")
            pages[0].close()
            paths.append(out)
        return paths

    if ext == ".pptx":
        if IS_WINDOWS and not Path(LIBREOFFICE_PATH).exists():
            raise RuntimeError(
                f"LibreOffice not found at '{LIBREOFFICE_PATH}'. "
                "Install from https://www.libreoffice.org or set LIBREOFFICE_PATH."
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


# ── Step 2: script generation ─────────────────────────────────────────────────

def _generate_scripts(image_paths: list[str]) -> list[str]:
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set — using placeholder scripts.")
        return [f"This is slide {i + 1}." for i in range(len(image_paths))]

    try:
        from groq import Groq

        client = Groq(api_key=GROQ_API_KEY)
        prompt = (
            "You are an enthusiastic educational content creator making short-form study videos. "
            "Analyse this slide and write a 2-4 sentence spoken narration that:\n"
            "1. Opens with a hook — a surprising fact, bold statement, or question\n"
            "2. Explains the core concept in simple, conversational language\n"
            "3. Ends with a memorable one-line takeaway\n"
            "Write naturally as if speaking to a student, not reading a textbook. "
            "Do NOT say 'slide', 'image', or 'figure'. Keep it under 65 words."
        )

        scripts = []
        for path in image_paths:
            with open(path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
            response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                max_tokens=300,
            )
            scripts.append(response.choices[0].message.content.strip())
            del image_b64
        return scripts

    except Exception:
        logger.exception("Groq call failed — falling back to placeholders.")
        return [f"Slide {i + 1}." for i in range(len(image_paths))]


# ── Step 3: audio synthesis ───────────────────────────────────────────────────

def _generate_audio(scripts: list[str], output_dir: str) -> list[str]:
    audio_dir = os.path.join(output_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    try:
        import asyncio
        import edge_tts

        paths = [os.path.join(audio_dir, f"audio_{i:03d}.mp3") for i in range(len(scripts))]

        async def _synth_all() -> None:
            for script, path in zip(scripts, paths):
                communicate = edge_tts.Communicate(script, voice="en-US-AriaNeural")
                await communicate.save(path)

        asyncio.run(_synth_all())
        return paths

    except Exception:
        logger.exception("edge-tts failed — generating silent stubs.")
        return [_silent_stub(os.path.join(audio_dir, f"audio_{i:03d}.mp3"), 4) for i in range(len(scripts))]


def _silent_stub(path: str, duration_s: int = 3) -> str:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(duration_s), path],
        check=True, capture_output=True,
    )
    return path


# ── Step 4: subtitle generation ───────────────────────────────────────────────

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


# ── Step 5: video render ──────────────────────────────────────────────────────

def _render_video(
    job_id: str,
    image_paths: list[str],
    audio_paths: list[str],
    subtitle_data: list[dict],
    temp_dir: str,
    jobs: dict | None = None,
    scripts: list[str] | None = None,
) -> str:
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
        _ffmpeg_fallback(image_paths, audio_paths, output_path, scripts, jobs, job_id)

    return output_path


def _ffmpeg_fallback(
    image_paths: list[str],
    audio_paths: list[str],
    output_path: str,
    scripts: list[str] | None = None,
    jobs: dict | None = None,
    job_id: str | None = None,
) -> None:
    """
    Stitch slides + audio into a 1080×1920 vertical MP4.
    Layout: blurred background fill + centered slide + caption bar at bottom.
    """
    segment_dir = os.path.dirname(output_path)
    segments = []
    n = len(image_paths)

    for i, (img, aud) in enumerate(zip(image_paths, audio_paths)):
        logger.info("Encoding slide %d/%d…", i + 1, n)
        seg = os.path.join(segment_dir, f"_seg_{i:03d}.mp4")
        duration = _audio_duration(aud)

        script_text = (scripts[i] if scripts and i < len(scripts) else "").strip()
        caption_path = os.path.join(segment_dir, f"_cap_{i:03d}.txt")
        if script_text:
            wrapped = "\n".join(textwrap.wrap(script_text, width=36))
            with open(caption_path, "w", encoding="utf-8") as f:
                f.write(wrapped)

        filter_complex = (
            "[0:v]split=2[v1][v2];"
            "[v1]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,boxblur=20:5[bg];"
            "[v2]scale=1080:1440:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=x=(W-w)/2:y=(H-h)/2-60[ov]"
        )
        if script_text:
            filter_complex += (
                f";[ov]drawtext=textfile={caption_path}"
                ":fontcolor=white:fontsize=34:x=30:y=h-230"
                ":box=1:boxcolor=black@0.65:boxborderw=15:line_spacing=8[v]"
            )
            video_map = "[v]"
        else:
            video_map = "[ov]"

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-loop", "1", "-i", img,
                "-i", aud,
                "-filter_complex", filter_complex,
                "-map", video_map,
                "-map", "1:a",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest", "-t", str(duration),
                "-threads", "2",
                seg,
            ],
            check=True,
            capture_output=True,
        )
        segments.append(seg)

        try:
            os.remove(img)
            if script_text:
                os.remove(caption_path)
        except OSError:
            pass

        if jobs is not None and job_id is not None:
            jobs[job_id]["progress"] = 75 + int(20 * (i + 1) / n)

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
