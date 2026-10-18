"""MIMIC web server: upload a clip, get the tracks, the steps, the program and its replay.

    .venv/bin/uvicorn server:app --port 8730

Env:
  MIMIC_RUNS          where runs are kept (default ./runs)
  MIMIC_ARM           sim (default) | so101
  MIMIC_SO101_PORT    serial port of the SO-101 / Thenar follower, e.g. /dev/tty.usbmodem1101
  MIMIC_THENAR_ARMS   path to the thenar-arms repo, for the SO-101 table guard
  META_API_KEY        Meta Model API key: enables the Muse Spark writer and SAM 3.1 (paid; only
                      used when picked in the page or with MIMIC_WRITER=muse-spark)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from mimic import arm as A
from mimic import pipeline, tracks
from mimic.synth import make_sample
from mimic.writer import MuseSparkWriter

ROOT = Path(__file__).resolve().parent
RUNS = Path(os.getenv("MIMIC_RUNS", ROOT / "runs"))
RUNS.mkdir(parents=True, exist_ok=True)
SAMPLE = ROOT / "samples" / "sample.mp4"
MAX_BYTES = 400 * 1024 * 1024
RUN_ID = re.compile(r"^[a-z0-9]{1,16}$")
log = logging.getLogger("mimic.server")

app = FastAPI(title="MIMIC")


def make_arm() -> A.Arm:
    if os.getenv("MIMIC_ARM", "sim") == "so101":
        return A.SO101Arm(os.environ["MIMIC_SO101_PORT"], A.load_guard(os.getenv("MIMIC_THENAR_ARMS")))
    return A.SimArm()


ARM = make_arm()
RUNNING = {"run": None, "waypoint": -1, "label": "", "task": None, "error": None, "connected": False}


def browser_copy(src: Path, dst: Path) -> Path:
    """H.264 MP4 the browser can play (phone .mov / HEVC / mp4v are re-encoded when ffmpeg exists)."""
    if not shutil.which("ffmpeg"):
        return src
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name",
                            "-of", "csv=p=0", str(src)], capture_output=True, text=True)
    if probe.stdout.strip() == "h264" and src.suffix.lower() == ".mp4":
        return src
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-t", str(tracks.MAX_SECONDS), "-an",
                    "-vf", "scale='min(1280,iw)':-2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
                    "-movflags", "+faststart", str(dst)], check=True)
    return dst


def save(run_id: str, result: dict, clip: Path) -> dict:
    result["run_id"] = run_id
    result["video"] = f"/runs/{run_id}/{clip.name}"
    (RUNS / run_id / "result.json").write_text(json.dumps(result))
    return result


def load(run_id: str) -> dict:
    if not RUN_ID.match(run_id) or not (RUNS / run_id / "result.json").exists():
        raise HTTPException(404, "no such run")
    return json.loads((RUNS / run_id / "result.json").read_text())


@app.get("/api/health")
def health():
    return {"ok": True, "trackers": tracks.available(), "writers": {"rules": True, "muse-spark": MuseSparkWriter.configured()},
            "arm": ARM.name}


def _pick(name: str | None, allowed: set[str], what: str) -> str | None:
    if name in (None, "", "auto"):
        return None
    if name not in allowed:
        raise HTTPException(400, f"unknown {what} {name!r}")
    return name


@app.post("/api/analyze")
async def analyze(video: UploadFile = File(...), prompts: str = Form(""), tracker: str = Form("color"),
                  writer: str = Form("rules"), corners: str = Form("")):
    tracker = _pick(tracker, {"color", "mediapipe", "sam3"}, "tracker") or "color"
    writer = _pick(writer, {"rules", "muse-spark"}, "writer") or "rules"
    try:
        corners_v = json.loads(corners) if corners else None
    except json.JSONDecodeError:
        raise HTTPException(400, "corners must be JSON: four [x, y] points")
    run_id = uuid.uuid4().hex[:10]
    d = RUNS / run_id
    d.mkdir()
    ext = Path(video.filename or "").suffix.lower()
    src = d / ("input" + (ext if re.fullmatch(r"\.[a-z0-9]{2,5}", ext) else ".mp4"))
    size = 0
    with src.open("wb") as f:
        while chunk := await video.read(1 << 20):
            size += len(chunk)
            if size > MAX_BYTES:
                shutil.rmtree(d)
                raise HTTPException(413, "clip is over 400 MB; trim it to the task")
            f.write(chunk)
    try:
        clip = await run_in_threadpool(browser_copy, src, d / "clip.mp4")
        result = await run_in_threadpool(pipeline.run, clip, prompts, tracker, writer, corners_v)
    except pipeline.ClipRejected as e:
        shutil.rmtree(d, ignore_errors=True)
        return JSONResponse({"detail": str(e), "reason": e.reason}, status_code=422)
    except (ValueError, RuntimeError, NotImplementedError, subprocess.CalledProcessError) as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(422, str(e))
    return save(run_id, result, clip)


@app.post("/api/sample")
async def sample(writer: str = Form("rules")):
    writer = _pick(writer, {"rules", "muse-spark"}, "writer") or "rules"
    if not SAMPLE.exists():
        await run_in_threadpool(make_sample, SAMPLE)
    truth = json.loads(SAMPLE.with_suffix(".truth.json").read_text())
    run_id = "sample" if writer == "rules" else "samplemuse"
    d = RUNS / run_id
    d.mkdir(exist_ok=True)
    clip = d / "clip.mp4"
    if not clip.exists() or clip.stat().st_mtime < SAMPLE.stat().st_mtime:
        shutil.copy(SAMPLE, clip)
    result = await run_in_threadpool(pipeline.run, clip, truth["prompts"], "color", writer, None, None, truth)
    return save(run_id, result, clip)


@app.post("/api/recheck/{run_id}")
async def recheck(run_id: str, body: dict):
    result = load(run_id)
    prog = body.get("program")
    if not isinstance(prog, dict):
        raise HTTPException(400, "send {\"program\": {...}}")
    out = pipeline.recheck(prog, result)
    result.update(out)
    (RUNS / run_id / "result.json").write_text(json.dumps(result))
    return out


@app.post("/api/execute/{run_id}")
async def execute(run_id: str):
    result = load(run_id)
    if RUNNING["task"] and not RUNNING["task"].done():
        raise HTTPException(409, "the arm is already running a program")
    prog = {"ok": result["check"]["ok"], "waypoints": result["replay"]["waypoints"]}
    if not prog["ok"]:
        raise HTTPException(422, "the program has unresolved issues; fix them before running it on an arm")

    async def go():
        RUNNING.update(run=run_id, error=None)
        try:
            if not RUNNING["connected"]:
                await ARM.connect()
                RUNNING["connected"] = True
            ARM.clear_stop()
            await A.replay(prog, ARM, on_step=lambda i, w: RUNNING.update(waypoint=i, label=w.get("label", "")))
            RUNNING.update(label="done")
        except A.Stopped:
            RUNNING.update(label="stopped")
        except Exception as e:  # serial errors, faults
            RUNNING.update(label="failed", error=str(e))
        finally:
            RUNNING["waypoint"] = -1

    RUNNING["task"] = asyncio.create_task(go())
    return {"started": True, "backend": ARM.name}


@app.post("/api/stop")
async def stop():
    await ARM.stop()
    return {"stopped": True}


@app.get("/api/arm")
def arm_state():
    busy = bool(RUNNING["task"] and not RUNNING["task"].done())
    return {**ARM.state(), "busy": busy, "run": RUNNING["run"], "waypoint": RUNNING["waypoint"],
            "label": RUNNING["label"], "error": RUNNING["error"]}


@app.get("/runs/{run_id}/{name}")
def run_file(run_id: str, name: str):
    if not RUN_ID.match(run_id) or name not in ("clip.mp4", "input.mp4", "result.json") and not re.fullmatch(r"input\.[a-z0-9]{2,5}", name):
        raise HTTPException(404)
    p = RUNS / run_id / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


app.mount("/web", StaticFiles(directory=ROOT / "web"), name="web")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8730")))
