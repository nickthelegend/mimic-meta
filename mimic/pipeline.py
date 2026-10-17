"""Clip -> tracks -> steps -> program -> checked replay, in one call.

    from mimic.pipeline import run
    result = run("clip.mp4", ["hand", "red block", "blue bowl"])
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import cv2

from . import program as P
from .calibrate import Calibration
from .segment import score, segment
from .tracks import FrameReader, Tracks, colour_of, get_tracker
from .writer import DEFAULT_HEIGHT, RuleWriter, get_writer

log = logging.getLogger("mimic.pipeline")

SWATCH = {"red": "#d8463b", "orange": "#ee8a2c", "yellow": "#e9c23a", "green": "#3f9f4a", "teal": "#2aa198",
          "cyan": "#2aa198", "blue": "#2f62c9", "purple": "#7a52c7", "violet": "#7a52c7", "pink": "#e06a9a", "magenta": "#c94aa8"}


def scene(tracks: Tracks, calib: Calibration, heights: dict | None = None) -> list[dict]:
    """Every tracked object where it first appears, in table metres, for the 3-D replay."""
    out = []
    for t in tracks.objects():
        if not t.frames:
            continue
        fs = t.frames[: max(3, min(10, len(t.frames)))]
        c = [sum(f["c"][k] for f in fs) / len(fs) for k in range(2)]
        f = fs[len(fs) // 2]
        rnd = f["size"][0] < 1.18 * max(f["size"][1], 1e-6) and f.get("fill", 1) < 0.88
        col = colour_of(t.label)
        out.append({"label": t.label, "m": calib.point(c), "yaw": None if rnd else round(calib.angle(c, f["yaw"]), 1),
                    "size_m": [round(calib.metres(c, s), 4) for s in f["size"]], "round": bool(rnd),
                    "color": SWATCH.get(col, "#8a8f94"), "height_m": (heights or {}).get(t.label, DEFAULT_HEIGHT)})
    return out


def key_frames(video: str | Path, times: list[float], width: int = 512) -> list[bytes]:
    r = FrameReader(video, width)
    want = sorted({max(0, int(t * r.fps)) for t in times})
    out = []
    for i, f in enumerate(r):
        if i in want:
            ok, jpg = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                out.append(jpg.tobytes())
        if i >= want[-1]:
            break
    return out


def run(video: str | Path, prompts=None, tracker: str = "color", writer: str | None = None,
        corners=None, heights: dict | None = None, truth: dict | None = None) -> dict:
    timings = {}
    t0 = time.perf_counter()
    tracks = get_tracker(tracker).track(video, prompts)
    timings["track_s"] = round(time.perf_counter() - t0, 2)
    calib = Calibration.from_corners(corners) if corners else Calibration.default(tracks.width, tracks.height)
    t1 = time.perf_counter()
    seg = segment(tracks, calib)
    timings["segment_s"] = round(time.perf_counter() - t1, 3)
    heights = heights or (truth or {}).get("heights")
    objs = scene(tracks, calib, heights)
    at = {o["label"]: o["m"] for o in objs}
    t2 = time.perf_counter()
    w = get_writer(writer)
    fallback = None
    try:
        frames = None
        if w.name == "muse-spark":
            picks = [s["t"] for s in seg["steps"] if s["kind"] == "pick"]
            frames = key_frames(video, [0.0, *picks, (tracks.n_frames - 1) / tracks.fps])
        written = w.write(seg["steps"], heights=heights, frames=frames, objects_at=at)
    except Exception as e:  # the API is down, the key is wrong, the reply isn't JSON: keep working offline
        log.warning("%s failed (%s); falling back to the rules", w.name, e)
        fallback = f"{w.name} failed: {e}"
        written = RuleWriter().write(seg["steps"], heights=heights)
    timings["write_s"] = round(time.perf_counter() - t2, 3)
    compiled = P.compile(written, at)
    result = {
        "clip": {"fps": tracks.fps, "width": tracks.width, "height": tracks.height, "n_frames": tracks.n_frames,
                 "seconds": round(tracks.n_frames / tracks.fps, 2)},
        "tracker": tracks.backend, "writer": written.get("writer", w.name), "fallback": fallback,
        "prompts": [t.label for t in tracks.tracks],
        "tracks": tracks.to_json()["tracks"], "hand_seen": seg["hand_seen"],
        "steps": seg["steps"], "calibration": seg["calibration"], "scene": objs,
        "program": P.strip(compiled), "check": {"ok": compiled["ok"], "issues": compiled["issues"],
                                                 "duration_s": compiled["duration_s"], "waypoints": len(compiled["waypoints"])},
        "replay": {"rate": 25, "waypoints": compiled["waypoints"], "samples": compiled["samples"],
                   "objects_end": compiled["objects_end"]},
        "timings": timings,
    }
    if truth:
        result["score"] = score(seg, truth, calib)
    return result


def recheck(program: dict, result: dict) -> dict:
    """The user edited the program in the page: compile and check it again."""
    at = {o["label"]: o["m"] for o in result.get("scene", [])}
    compiled = P.compile({**program, "writer": program.get("writer", "edited")}, at)
    return {"program": P.strip(compiled), "check": {"ok": compiled["ok"], "issues": compiled["issues"],
                                                    "duration_s": compiled["duration_s"], "waypoints": len(compiled["waypoints"])},
            "replay": {"rate": 25, "waypoints": compiled["waypoints"], "samples": compiled["samples"],
                       "objects_end": compiled["objects_end"]}}


if __name__ == "__main__":
    import sys

    clip = sys.argv[1]
    truth_p = Path(clip).with_suffix(".truth.json")
    truth = json.loads(truth_p.read_text()) if truth_p.exists() else None
    r = run(clip, sys.argv[2] if len(sys.argv) > 2 else (truth or {}).get("prompts"), truth=truth)
    print(json.dumps({k: r[k] for k in ("steps", "check", "timings")} | ({"score": r["score"]} if truth else {}), indent=1))
