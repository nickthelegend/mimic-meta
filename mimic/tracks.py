"""Hand and object tracks from a video, behind one interface.

    tracker = get_tracker("color")            # or "mediapipe", "sam3"
    tracks = tracker.track("clip.mp4", ["hand", "red block", "blue bowl"])

Prompts are short noun phrases, exactly what SAM 3.1's promptable concept segmentation
takes, so swapping the stand-in for SAM 3.1 changes nothing downstream. Every backend
returns the same Tracks: per prompt, per frame, a box, a centroid, an outline polygon,
the object's on-table yaw, and for hands (when the backend can tell) the pinch aperture.

Backends:
  ColorTracker      OpenCV only. Objects by colour word in the prompt ("red block"),
                    hands by skin tone. Works offline on the synthetic sample and on real
                    clips of brightly coloured objects on a plain table.
  MediaPipeTracker  MediaPipe hand landmarks (pinch aperture from thumb and index tips)
                    plus ColorTracker for objects. Needs `pip install mediapipe` and the
                    hand_landmarker.task model file (MIMIC_HAND_MODEL).
  Sam3Tracker       SAM 3.1 on the Meta Model API, one text concept per request (META_API_KEY).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

MAX_W = 640  # frames are analysed at this width; coordinates are reported in the clip's pixels


@dataclass
class Track:
    id: int
    label: str
    kind: str  # "hand" | "object"
    frames: list[dict] = field(default_factory=list)  # {"i", "box", "c", "poly", "yaw", "size", "ap"?}


@dataclass
class Tracks:
    fps: float
    width: int
    height: int
    n_frames: int
    backend: str
    tracks: list[Track] = field(default_factory=list)

    def hands(self) -> list[Track]:
        return [t for t in self.tracks if t.kind == "hand"]

    def objects(self) -> list[Track]:
        return [t for t in self.tracks if t.kind == "object"]

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(d: dict) -> "Tracks":
        return Tracks(**{**d, "tracks": [Track(**t) for t in d["tracks"]]})


class Tracker(Protocol):
    name: str

    def track(self, video: str | Path, prompts: list[str]) -> Tracks: ...


HAND_WORDS = {"hand", "hands", "my hand", "left hand", "right hand", "fingers"}


def is_hand(prompt: str) -> bool:
    return prompt.strip().lower() in HAND_WORDS


def parse_prompts(text: str | list[str] | None) -> list[str]:
    if text is None:
        return []
    items = text if isinstance(text, list) else re.split(r"[,;\n]+", text)
    out = []
    for p in items:
        p = p.strip().lower()
        if p and p not in out:
            out.append(p)
    return out


# ------------------------------------------------------------------ OpenCV stand-in ---

# OpenCV hue is 0..179. Each colour word maps to one or two hue bands of saturated pixels.
HUES = {
    "red": [(0, 8), (170, 180)], "orange": [(9, 20)], "yellow": [(21, 34)], "green": [(35, 85)],
    "teal": [(86, 96)], "cyan": [(86, 96)], "blue": [(97, 128)], "purple": [(129, 155)],
    "violet": [(129, 155)], "pink": [(156, 169)], "magenta": [(150, 169)],
}
SAT_MIN, VAL_MIN = 120, 60


def colour_of(prompt: str) -> str | None:
    for w in prompt.lower().split():
        if w in HUES:
            return w
    return None


def _hue_mask(hsv: np.ndarray, colour: str) -> np.ndarray:
    m = np.zeros(hsv.shape[:2], np.uint8)
    for lo, hi in HUES[colour]:
        m |= cv2.inRange(hsv, (lo, SAT_MIN, VAL_MIN), (hi, 255, 255))
    return m


def _skin_mask(bgr: np.ndarray, hsv: np.ndarray) -> np.ndarray:
    ycc = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    m = cv2.inRange(ycc, (40, 138, 80), (255, 178, 128))
    m &= cv2.inRange(hsv, (0, 35, 70), (25, 150, 255)) | cv2.inRange(hsv, (165, 35, 70), (180, 150, 255))
    return m


KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))


def _blob(mask: np.ndarray, min_area: float, prev_c=None):
    """The component to follow: the largest one, or near the last position if several are big."""
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, KERNEL)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, KERNEL, iterations=2)
    cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cs = [c for c in cs if cv2.contourArea(c) >= min_area]
    if not cs:
        return None
    if prev_c is not None and len(cs) > 1:
        big = max(cv2.contourArea(c) for c in cs)
        cs = [c for c in cs if cv2.contourArea(c) > 0.4 * big]
        return min(cs, key=lambda c: np.hypot(*(c.reshape(-1, 2).mean(0) - prev_c)))
    return max(cs, key=cv2.contourArea)


def describe(contour: np.ndarray, scale: float) -> dict:
    """Box, centroid, outline and on-table yaw of a contour, in clip pixels."""
    c = contour.astype(np.float32) / scale
    x, y, w, h = cv2.boundingRect(c)
    m = cv2.moments(c)
    cx, cy = (m["m10"] / m["m00"], m["m01"] / m["m00"]) if m["m00"] else (x + w / 2, y + h / 2)
    eps = 0.01 * cv2.arcLength(c, True)
    poly = cv2.approxPolyDP(c, eps, True).reshape(-1, 2)
    (_, _), (rw, rh), ang = cv2.minAreaRect(c)
    if rw < rh:  # yaw of the long side, degrees, image x axis = 0, counter-clockwise on screen
        rw, rh, ang = rh, rw, ang + 90
    yaw = -((ang + 90) % 180 - 90)
    return {"box": [round(x), round(y), round(w), round(h)], "c": [round(cx, 1), round(cy, 1)],
            "poly": poly.round().astype(int).tolist(), "yaw": round(float(yaw), 1),
            "size": [round(float(rw), 1), round(float(rh), 1)],
            "fill": round(float(cv2.contourArea(c)) / max(float(rw * rh), 1e-6), 2)}


MAX_FPS, MAX_SECONDS = 30, 120  # slow-motion clips are thinned to 30 fps; longer clips are cut


class FrameReader:
    """Streams a clip's frames already shrunk to max_w, so a long 4K phone clip never sits in
    memory. Frames past MAX_SECONDS are dropped and high-fps clips are thinned to MAX_FPS."""

    def __init__(self, video: str | Path, max_w: int = MAX_W):
        self.video, self.max_w = str(video), max_w
        cap = cv2.VideoCapture(self.video)
        if not cap.isOpened():
            raise ValueError(f"can't open video {video}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.src_fps = fps if 1 <= fps <= 1000 else 30.0
        self.step = max(1, round(self.src_fps / MAX_FPS))
        self.fps = self.src_fps / self.step
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        ok, f = cap.read()  # the first frame's shape, after the phone's rotation is applied
        cap.release()
        if not ok:
            raise ValueError("the video has no readable frames")
        self.height, self.width = f.shape[:2]
        self.scale = min(1.0, max_w / self.width)
        self.n_est = min(int(MAX_SECONDS * self.fps), -(-count // self.step)) if count > 0 else 0

    def __iter__(self):
        cap = cv2.VideoCapture(self.video)
        n, k = 0, 0
        limit = int(MAX_SECONDS * self.fps)
        while n < limit:
            ok, f = cap.read()
            if not ok:
                break
            k += 1
            if (k - 1) % self.step:
                continue
            if self.scale < 1:
                f = cv2.resize(f, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_AREA)
            yield f
            n += 1
        cap.release()


def read_frames(video: str | Path, max_w: int = MAX_W):
    """All frames of a (short) clip, shrunk. For key frames and tests, not for tracking."""
    r = FrameReader(video, max_w)
    return r.fps, list(r)


class ColorTracker:
    name = "color"

    def __init__(self, hands: bool = True):
        self.hands = hands

    def track(self, video, prompts) -> Tracks:
        reader = FrameReader(video)
        prompts = parse_prompts(prompts)
        it = iter(reader)
        head = []
        if not prompts:  # look at the first half second to decide what to follow
            for f in it:
                head.append(f)
                if len(head) >= max(1, int(reader.fps / 2)):
                    break
            prompts = self.auto_prompts(head)
        tracks = [Track(i, p, "hand" if is_hand(p) else "object") for i, p in enumerate(prompts)]
        state = {}
        n = 0
        for f in [*head, *it]:
            self.process(f, n, tracks, reader.scale, state)
            n += 1
        tracks = [t for t in tracks if t.frames or t.kind == "hand"]
        return Tracks(fps=reader.fps, width=reader.width, height=reader.height, n_frames=n, backend=self.name, tracks=tracks)

    def process(self, small: np.ndarray, fi: int, tracks: list[Track], scale: float, prev: dict) -> None:
        small = cv2.GaussianBlur(small, (5, 5), 0)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        sat = cv2.inRange(hsv, (0, 150, 0), (180, 255, 255))  # strongly coloured: never skin
        area = small.shape[0] * small.shape[1]
        for t in tracks:
            if t.kind == "hand":
                if not self.hands:
                    continue
                mask = _skin_mask(small, hsv) & ~sat
                min_area = area * 0.004
            else:
                col = colour_of(t.label)
                if not col:
                    continue
                mask = _hue_mask(hsv, col)
                min_area = area * 0.0006
            c = _blob(mask, min_area, prev.get(t.id))
            if c is None:
                continue
            d = describe(c, scale)
            prev[t.id] = np.array(d["c"]) * scale
            t.frames.append({"i": fi, **d})

    @staticmethod
    def auto_prompts(frames) -> list[str]:
        """No prompts given: the hand, plus every colour with a sizeable blob in the first frames."""
        found = []
        for f in frames:
            hsv = cv2.cvtColor(cv2.GaussianBlur(f, (5, 5), 0), cv2.COLOR_BGR2HSV)
            area = f.shape[0] * f.shape[1]
            for col in ("red", "orange", "yellow", "green", "blue", "purple", "pink"):
                if col not in found and _blob(_hue_mask(hsv, col), area * 0.0015) is not None:
                    found.append(col)
        return ["hand"] + [f"{c} object" for c in found]


# ------------------------------------------------------------------ MediaPipe hands ---

class MediaPipeTracker:
    """MediaPipe HandLandmarker for the hand (outline = hull of the 21 landmarks, aperture =
    thumb-to-index distance over palm length), ColorTracker for everything else."""

    name = "mediapipe"

    def __init__(self, model_path: str | None = None):
        import mediapipe as mp  # noqa: F401  (fail early if it isn't installed)

        self.model_path = model_path or os.getenv("MIMIC_HAND_MODEL", "models/hand_landmarker.task")
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"hand model not found at {self.model_path} (see README: MediaPipe)")

    def track(self, video, prompts) -> Tracks:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        reader = FrameReader(video)
        objs = [Track(i, p, "object") for i, p in enumerate(p for p in parse_prompts(prompts) if not is_hand(p))]
        hand = Track(len(objs), "hand", "hand")
        colour, state = ColorTracker(hands=False), {}
        opts = vision.HandLandmarkerOptions(base_options=BaseOptions(model_asset_path=self.model_path),
                                            running_mode=vision.RunningMode.VIDEO, num_hands=1)
        n = 0
        with vision.HandLandmarker.create_from_options(opts) as lm:
            for f in reader:
                colour.process(f, n, objs, reader.scale, state)
                img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
                res = lm.detect_for_video(img, int(n * 1000 / reader.fps))
                if res.hand_landmarks:
                    w, h = reader.width, reader.height
                    pts = np.array([[p.x * w, p.y * h] for p in res.hand_landmarks[0]], np.float32)
                    d = describe(cv2.convexHull(pts), 1.0)
                    palm = np.linalg.norm(pts[0] - pts[9]) or 1.0
                    d["ap"] = round(float(np.linalg.norm(pts[4] - pts[8]) / palm), 3)
                    d["tip"] = ((pts[4] + pts[8]) / 2).round(1).tolist()
                    hand.frames.append({"i": n, **d})
                n += 1
        return Tracks(fps=reader.fps, width=reader.width, height=reader.height, n_frames=n, backend=self.name,
                      tracks=[hand, *[t for t in objs if t.frames]])


# ------------------------------------------------------------------ SAM 3.1 ---

class Sam3Tracker:
    """SAM 3.1 on the Meta Model API (model "sam-3.1", POST /v1/responses). The hosted API
    takes one text concept per request, so each prompt is one request on the same uploaded
    clip (about $0.20 per 1,000 frames each: a paid call, only ever made when asked for).

    The reply is special-token text (boxes and masks per frame) that Meta's @meta-sam/parser
    decodes. Until that format is wired up from a real reply (README TODO), every raw reply is
    saved next to the clip and parse_reply() raises, so nothing guesses at masks."""

    name = "sam3"

    def __init__(self, base: str | None = None, key: str | None = None, model: str | None = None,
                 transport=None, timeout: float = 900):
        self.base = (base or os.getenv("MIMIC_SAM_BASE", "https://api.meta.ai/v1")).rstrip("/")
        self.key = key or os.getenv("META_API_KEY") or os.getenv("MUSE_API_KEY")
        self.model = model or os.getenv("MIMIC_SAM_MODEL", "sam-3.1")
        if not self.key:
            raise RuntimeError("META_API_KEY is not set (SAM 3.1 runs on the Meta Model API)")
        self.transport, self.timeout = transport, timeout

    def track(self, video, prompts) -> Tracks:
        import httpx

        reader = FrameReader(video)
        prompts = parse_prompts(prompts) or ["hand"]
        auth = {"Authorization": f"Bearer {self.key}"}
        with httpx.Client(transport=self.transport, timeout=self.timeout, headers=auth) as c:
            with open(video, "rb") as f:
                up = c.post(f"{self.base}/files", files={"file": (Path(video).name, f, "video/mp4")}, data={"purpose": "user_data"})
            up.raise_for_status()
            file_id = up.json()["id"]
            objects = []
            for p in prompts:
                r = c.post(f"{self.base}/responses", json={
                    "model": self.model, "metadata": {"mask_encoding": "one_bit"},
                    "input": [{"role": "user", "content": [{"type": "input_text", "text": p},
                                                           {"type": "input_video", "file_id": file_id}]}]})
                r.raise_for_status()
                reply = r.json()
                Path(video).with_suffix(f".sam-{re.sub(r'[^a-z0-9]+', '-', p)}.json").write_text(json.dumps(reply))
                objects += parse_reply(reply, p)
        return from_masks({"fps": reader.fps, "width": reader.width, "height": reader.height,
                           "n_frames": reader.n_est, "objects": objects}, prompts)


def parse_reply(reply: dict, prompt: str) -> list[dict]:
    """SAM 3.1 API reply -> [{"prompt", "obj_id", "frames": [{"i", "poly"}]}]. Not wired yet:
    the special-token format has to be checked against a real reply first."""
    raise NotImplementedError("SAM 3.1 reply parsing is not wired up yet; the raw reply was saved "
                              "next to the clip (see README TODO: SAM 3.1)")


def from_masks(d: dict, prompts: list[str]) -> Tracks:
    """Decoded SAM 3.1 masks -> Tracks. d is {"fps", "width", "height", "n_frames",
    "objects": [{"prompt", "obj_id", "frames": [{"i", "poly": [[x, y], ...]}]}]}: one outline
    polygon per object per frame (each mask's largest contour)."""
    tracks = []
    for k, o in enumerate(d["objects"]):
        t = Track(k, o["prompt"] if sum(p["prompt"] == o["prompt"] for p in d["objects"]) == 1
                  else f'{o["prompt"]} {o["obj_id"]}', "hand" if is_hand(o["prompt"]) else "object")
        for fr in o["frames"]:
            pts = np.array(fr["poly"], np.float32).reshape(-1, 1, 2)
            if len(pts) >= 3:
                t.frames.append({"i": fr["i"], **describe(pts, 1.0)})
        tracks.append(t)
    return Tracks(fps=d["fps"], width=d["width"], height=d["height"], n_frames=d["n_frames"],
                  backend="sam3", tracks=tracks)


def get_tracker(name: str = "color") -> Tracker:
    name = (name or "color").lower()
    if name == "color":
        return ColorTracker()
    if name == "mediapipe":
        return MediaPipeTracker()
    if name in ("sam3", "sam3.1", "sam"):
        return Sam3Tracker()
    raise ValueError(f"unknown tracker {name!r}")


def available() -> dict:
    out = {"color": True, "mediapipe": False, "sam3": bool(os.getenv("META_API_KEY") or os.getenv("MUSE_API_KEY"))}
    try:
        import mediapipe  # noqa: F401

        out["mediapipe"] = Path(os.getenv("MIMIC_HAND_MODEL", "models/hand_landmarker.task")).exists()
    except ImportError:
        pass
    return out
