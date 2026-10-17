"""A synthetic demonstration clip with exact ground truth, so the whole pipeline can be
run and scored offline before any real filming.

    python -m mimic.synth samples/sample.mp4     # also writes samples/sample.truth.json

Top-down view of the arm's mat. A hand comes in from the robot's side, puts the red
block in the blue bowl (turning it a little on the way), then slides the green block
to the right and turns it. Rendered with skin, shading, shadows and sensor noise so
the OpenCV stand-in has to work for it, not read pixels it drew itself.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

W, H, FPS, SECONDS = 960, 540, 30, 10.0
SKIN = np.array([150, 182, 228], float)  # BGR
TABLE = np.array([198, 203, 207], float)

OBJECTS = {
    "red block": {"c": (300, 232), "size": (58, 58), "yaw": 20, "col": (38, 40, 206), "h": 0.03},
    "green block": {"c": (520, 382), "size": (78, 44), "yaw": -10, "col": (70, 160, 40), "h": 0.025},
    "blue bowl": {"c": (690, 190), "r": 64, "col": (176, 92, 28), "h": 0.04},
}
# (t, grasp point, aperture px, what the hand holds); objects turn by TURN while carried
KEYS = [
    (0.0, (470, 640), 92, None), (1.4, (300, 232), 92, None), (1.8, (300, 232), 60, "red block"),
    (3.6, (690, 190), 60, "red block"), (3.9, (690, 190), 60, "red block"), (4.2, (690, 190), 92, None),
    (5.6, (520, 382), 92, None), (6.0, (520, 382), 46, "green block"), (7.6, (770, 408), 46, "green block"),
    (7.9, (770, 408), 46, "green block"), (8.2, (770, 408), 92, None), (9.6, (560, 650), 92, None),
    (10.0, (560, 650), 92, None),
]
TURN = {"red block": 25.0, "green block": 45.0}
CARRIES = [  # ground truth: when the object starts and stops moving
    {"object": "red block", "t_pick": 1.8, "t_place": 3.6, "into": "blue bowl"},
    {"object": "green block", "t_pick": 6.0, "t_place": 7.6, "into": None},
]
PROMPTS = ["hand", "red block", "green block", "blue bowl"]


def ease(u: float) -> float:
    return u * u * u * (u * (u * 6 - 15) + 10)  # minimum-jerk profile, like a real reach


def hand_at(t: float):
    """Grasp point (between thumb and index tips) and pinch aperture in pixels at time t."""
    for k0, k1 in zip(KEYS, KEYS[1:]):
        if k0[0] <= t <= k1[0]:
            u = ease((t - k0[0]) / (k1[0] - k0[0]))
            g = np.array(k0[1], float) + (np.array(k1[1], float) - np.array(k0[1], float)) * u
            return g, k0[2] + (k1[2] - k0[2]) * u
    return np.array(KEYS[-1][1], float), KEYS[-1][2]


def object_states(t: float) -> dict:
    """Where each object is at time t (centre, yaw), replaying the key list from the start."""
    st = {k: {"c": np.array(v["c"], float), "yaw": float(v.get("yaw", 0))} for k, v in OBJECTS.items()}
    for k0, k1 in zip(KEYS, KEYS[1:]):
        name = k0[3]
        if name and k1[3] == name and k0[1] != k1[1]:
            if t <= k0[0]:
                break
            u = ease(min(1.0, (t - k0[0]) / (k1[0] - k0[0])))
            a, b = np.array(k0[1], float), np.array(k1[1], float)
            st[name]["c"] = a + (b - a) * u
            st[name]["yaw"] = OBJECTS[name]["yaw"] + TURN[name] * u
            st[name]["lift"] = math.sin(math.pi * u)
            if t < k1[0]:
                break
            st[name].pop("lift")
    return st


def rot_rect(c, size, yaw):
    return cv2.boxPoints(((float(c[0]), float(c[1])), (float(size[0]), float(size[1])), -float(yaw))).astype(np.float32)


def render(t: float, rng: np.random.Generator, base: np.ndarray) -> np.ndarray:
    img = base.copy()
    st = object_states(t)
    shadow = np.zeros((H, W), np.float32)
    layers = []
    for name in ("blue bowl", "green block", "red block"):  # bowl underneath, so the block sits in it
        o, s = OBJECTS[name], st[name]
        lift = s.get("lift", 0.0)
        off = np.array([10, 12]) * (0.5 + lift)
        if "r" in o:
            cv2.circle(shadow, tuple((s["c"] + off * 0.6).astype(int)), o["r"], 1.0, -1, cv2.LINE_AA)
            layers.append(("bowl", o, s))
        else:
            sz = np.array(o["size"]) * (1 + 0.07 * lift)
            cv2.fillConvexPoly(shadow, rot_rect(s["c"] + off, sz, s["yaw"]).astype(np.int32), 1.0, cv2.LINE_AA)
            layers.append(("block", o, s, sz))
    shadow = cv2.GaussianBlur(shadow, (0, 0), 9)
    img *= (1 - 0.28 * shadow[..., None])
    for layer in layers:
        if layer[0] == "bowl":
            _, o, s = layer
            c = tuple(s["c"].astype(int))
            cv2.circle(img, c, o["r"], np.array(o["col"]) * 0.78, -1, cv2.LINE_AA)
            cv2.circle(img, c, o["r"] - 10, o["col"], -1, cv2.LINE_AA)
            cv2.circle(img, (c[0] - 12, c[1] - 14), o["r"] - 34, np.minimum(255, np.array(o["col"]) * 1.25), -1, cv2.LINE_AA)
        else:
            _, o, s, sz = layer
            pts = rot_rect(s["c"], sz, s["yaw"])
            cv2.fillConvexPoly(img, pts.astype(np.int32), np.array(o["col"]) * 0.82, cv2.LINE_AA)
            inner = rot_rect(s["c"] - 2, sz * 0.82, s["yaw"])
            cv2.fillConvexPoly(img, inner.astype(np.int32), o["col"], cv2.LINE_AA)
    draw_hand(img, t)
    img += rng.normal(0, 3.0, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def draw_hand(img: np.ndarray, t: float) -> None:
    g, ap = hand_at(t)
    anchor = np.array([480 + (g[0] - 480) * 0.35, 760.0])
    d = anchor - g
    d /= np.linalg.norm(d)
    n = np.array([-d[1], d[0]])
    palm = g + d * 80
    sh = np.zeros(img.shape[:2], np.float32)  # the hand's own soft shadow
    for a, b, wd in [(palm + d * 30, anchor, 76), (g + n * ap / 2, palm + n * 24, 18), (g - n * ap / 2, palm - n * 24, 18)]:
        cv2.line(sh, tuple((a + 14).astype(int)), tuple((b + 14).astype(int)), 1.0, wd, cv2.LINE_AA)
    cv2.circle(sh, tuple((palm + 14).astype(int)), 46, 1.0, -1, cv2.LINE_AA)
    sh = cv2.GaussianBlur(sh, (0, 0), 10)
    img *= (1 - 0.22 * sh[..., None])

    def skin(k):
        return tuple(float(v) for v in SKIN * k)

    cv2.line(img, tuple((palm + d * 30).astype(int)), tuple(anchor.astype(int)), skin(0.9), 76, cv2.LINE_AA)  # forearm
    cv2.ellipse(img, tuple(palm.astype(int)), (46, 40), math.degrees(math.atan2(d[1], d[0])), 0, 360, skin(0.95), -1, cv2.LINE_AA)
    for side in (1, -1):  # thumb and index: the pinch
        tip = g + side * n * ap / 2
        root = palm + side * n * 24 - d * 22
        cv2.line(img, tuple(root.astype(int)), tuple(tip.astype(int)), skin(0.93), 18, cv2.LINE_AA)
        cv2.circle(img, tuple(tip.astype(int)), 9, skin(1.0), -1, cv2.LINE_AA)
    for k in range(3):  # curled fingers
        p = palm - d * 30 + n * (k - 1) * 18
        cv2.circle(img, tuple(p.astype(int)), 12, skin(0.9), -1, cv2.LINE_AA)
    cv2.ellipse(img, tuple((palm - d * 6).astype(int)), (30, 24), 0, 0, 360, skin(1.03), -1, cv2.LINE_AA)


def table() -> np.ndarray:
    rng = np.random.default_rng(7)
    img = np.ones((H, W, 3)) * TABLE
    grain = cv2.GaussianBlur(rng.normal(0, 1, (H, W)), (0, 0), 1.5)
    img += grain[..., None] * 5
    yy, xx = np.mgrid[0:H, 0:W]
    img *= (1 - 0.12 * (((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2))[..., None]
    for x, y, sx, sy in [(14, 14, 1, 1), (W - 14, 14, -1, 1), (W - 14, H - 14, -1, -1), (14, H - 14, 1, -1)]:
        cv2.line(img, (x, y), (x + 40 * sx, y), (70, 72, 74), 3, cv2.LINE_AA)  # mat corner marks
        cv2.line(img, (x, y), (x, y + 40 * sy), (70, 72, 74), 3, cv2.LINE_AA)
    return img


def make_sample(path: str | Path) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.with_suffix(".raw.mp4")
    vw = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    rng = np.random.default_rng(1)
    base = table()
    for i in range(int(SECONDS * FPS)):
        vw.write(render(i / FPS, rng, base))
    vw.release()
    if shutil.which("ffmpeg"):  # browsers can't play mp4v
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-crf", "20", "-movflags", "+faststart", str(path)], check=True)
        raw.unlink()
    else:
        raw.replace(path)
    truth = {"fps": FPS, "width": W, "height": H, "prompts": PROMPTS, "carries": [],
             "heights": {k: v["h"] for k, v in OBJECTS.items()}}
    for c in CARRIES:
        a, b = object_states(c["t_pick"] - 0.05)[c["object"]], object_states(SECONDS)[c["object"]]
        truth["carries"].append({**c, "from_px": a["c"].round(1).tolist(), "to_px": b["c"].round(1).tolist(),
                                 "yaw_from": round(a["yaw"], 1), "yaw_to": round(b["yaw"], 1)})
    path.with_suffix(".truth.json").write_text(json.dumps(truth, indent=1))
    return truth


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "samples/sample.mp4"
    print(json.dumps(make_sample(out), indent=1))
