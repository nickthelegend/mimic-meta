"""Tracks -> the task, as pick / move / place steps.

An object is *carried* when it moves a real distance while a hand is on it. Its
smoothed centroid speed has to rise above V_ON (and is followed down to V_OFF, so the
step starts and ends where the motion really does), last at least MIN_CARRY seconds,
and end somewhere else than it began. That rules out the wobble an occluding hand
causes on an object that never leaves its place. Each carry becomes

    pick  (where it was, how it was turned, how big it is)
    move  (the path it took, simplified)
    place (where it ended, how it was turned, what it was put into or onto)

Positions are reported in clip pixels and, through the calibration, in robot metres.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from .calibrate import Calibration
from .tracks import Track, Tracks

V_ON, V_OFF = 0.045, 0.015  # speed thresholds, in frame diagonals per second
MIN_CARRY = 0.3  # s
MERGE_GAP = 0.25  # s
MAX_GAP = 0.5  # s of missing detections that get interpolated
ROUND = 1.18  # long/short side ratio under which an object has no meaningful yaw


def series(track: Track, n: int, fps: float, key: str = "c") -> np.ndarray:
    """(n, 2) centroids per frame, NaN where unseen; short gaps filled linearly."""
    out = np.full((n, 2), np.nan)
    for f in track.frames:
        if f["i"] < n:
            out[f["i"]] = f[key]
    seen = np.where(~np.isnan(out[:, 0]))[0]
    for a, b in zip(seen, seen[1:]):
        if 1 < b - a <= MAX_GAP * fps:
            for k in range(2):
                out[a:b + 1, k] = np.linspace(out[a, k], out[b, k], b - a + 1)
    return out


def smooth(x: np.ndarray, win: int) -> np.ndarray:
    """Centred moving average over win frames, skipping NaNs; unseen frames stay NaN."""
    if win < 2:
        return x
    out = np.full_like(x, np.nan)
    h = win // 2
    for i in range(len(x)):
        seg = x[max(0, i - h): i + h + 1]
        seg = seg[~np.isnan(seg[:, 0])]
        if len(seg) and not np.isnan(x[i, 0]):
            out[i] = seg.mean(0)
    return out


def intervals(mask: np.ndarray) -> list[tuple[int, int]]:
    """Runs of True in mask, as inclusive (start, end) index pairs."""
    out, start = [], None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        elif not m and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def hand_distance(tracks: Tracks, n: int) -> list[dict[int, list]]:
    """Per frame, the outline of every hand seen."""
    polys = [dict() for _ in range(n)]
    for h in tracks.hands():
        for f in h.frames:
            if f["i"] < n:
                polys[f["i"]][h.id] = f["poly"]
    return polys


def near_hand(polys: dict, c, reach: float) -> bool:
    """Whether point c is inside, or within reach pixels of, any of these hand outlines."""
    for poly in polys.values():
        d = cv2.pointPolygonTest(np.array(poly, np.float32).reshape(-1, 1, 2), (float(c[0]), float(c[1])), True)
        if d >= -reach:
            return True
    return False


def frame_at(track: Track, i: int, before: bool, span: int) -> list[dict]:
    """The track's frames in the span frames before (or after) frame i, not including i."""
    fs = [f for f in track.frames if (i - span <= f["i"] < i if before else i < f["i"] <= i + span)]
    return fs


def median_pose(fs: list[dict]) -> dict | None:
    """Median position, size and yaw of these frames, with roundness and symmetry; None if empty."""
    if not fs:
        return None
    c = np.median([f["c"] for f in fs], 0)
    size = np.median([f["size"] for f in fs], 0)
    fill = float(np.median([f.get("fill", 1.0) for f in fs]))
    square = bool(size[0] < ROUND * max(size[1], 1e-6))
    rnd = square and fill < 0.88  # a disc fills ~79% of its bounding square, a block ~100%
    sym = 90 if square else 180  # a square block looks the same every 90 deg, a bar every 180
    k = 360 / sym
    yaws = np.radians([f["yaw"] for f in fs]) * k  # average on the wrapped circle
    yaw = math.degrees(math.atan2(np.sin(yaws).mean(), np.cos(yaws).mean())) / k
    return {"c": c.round(1).tolist(), "size": size.round(1).tolist(), "yaw": round(yaw, 1),
            "round": rnd, "sym": sym}


def rdp(pts: np.ndarray, eps: float) -> np.ndarray:
    """Simplify a polyline with Ramer-Douglas-Peucker at tolerance eps."""
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    ab = b - a
    L = np.linalg.norm(ab) or 1e-9
    rel = pts - a
    d = np.abs(ab[0] * rel[:, 1] - ab[1] * rel[:, 0]) / L
    k = int(np.argmax(d))
    if d[k] > eps:
        return np.vstack([rdp(pts[: k + 1], eps)[:-1], rdp(pts[k:], eps)])
    return np.array([a, b])


def inside(track: Track, i: int, c) -> bool:
    """Whether point c lies within the track's outline (convex hull) within 3 frames of i."""
    fs = [f for f in track.frames if abs(f["i"] - i) <= 3]
    for f in fs:
        hull = cv2.convexHull(np.array(f["poly"], np.float32).reshape(-1, 1, 2))  # a bowl's outline is a C while a hand covers it
        if cv2.pointPolygonTest(hull, (float(c[0]), float(c[1])), False) >= 0:
            return True
    return False


def segment(tracks: Tracks, calib: Calibration | None = None) -> dict:
    """Find every object carried by a hand and return the task as pick / move / place steps."""
    calib = calib or Calibration.default(tracks.width, tracks.height)
    n, fps = tracks.n_frames, tracks.fps
    diag = math.hypot(tracks.width, tracks.height)
    win = max(3, int(round(0.2 * fps)) | 1)
    polys = hand_distance(tracks, n)
    any_hand = any(h.frames for h in tracks.hands())
    carries = []
    for obj in tracks.objects():
        c = smooth(series(obj, n, fps), win)
        v = np.full(n, np.nan)
        v[1:] = np.linalg.norm(np.diff(c, axis=0), axis=1) * fps / diag
        v = np.nan_to_num(v)
        on = intervals(v > V_ON)
        # follow each burst down to V_OFF on both sides, then merge bursts split by short pauses
        grown = []
        for a, b in on:
            while a > 0 and v[a - 1] > V_OFF:
                a -= 1
            while b < n - 1 and v[b + 1] > V_OFF:
                b += 1
            if grown and a - grown[-1][1] <= MERGE_GAP * fps:
                grown[-1] = (grown[-1][0], max(b, grown[-1][1]))
            else:
                grown.append((a, b))
        span = int(0.3 * fps)
        for a, b in grown:
            if (b - a) / fps < MIN_CARRY:
                continue
            p0, p1 = median_pose(frame_at(obj, a, True, span)), median_pose(frame_at(obj, b, False, span))
            if not p0 or not p1:
                continue
            moved = math.dist(p0["c"], p1["c"])
            if moved < max(20.0, 0.4 * p0["size"][0]):
                continue
            reach = 0.6 * p0["size"][0] + 0.02 * diag
            held = [near_hand(polys[i], c[i], reach) for i in range(a, b + 1) if not np.isnan(c[i, 0])]
            frac = float(np.mean(held)) if held else 0.0
            if any_hand and frac < 0.5:
                continue  # it moved, but nobody was holding it (it fell, rolled, or the camera moved)
            # when the hand got there before, and left after
            g = a
            while g > 0 and near_hand(polys[g - 1], c[a], reach):
                g -= 1
            r = b
            while r < n - 1 and near_hand(polys[r + 1], c[b], reach):
                r += 1
            # its shape (size, yaw, round or not) from before the fingers touch it and after they let go
            for p, i, before in ((p0, g, True), (p1, r, False)):
                clear = median_pose(frame_at(obj, i, before, span))
                if clear:
                    p.update({k: clear[k] for k in ("size", "yaw", "round", "sym")})
            path = c[a:b + 1]
            path = path[~np.isnan(path[:, 0])]
            path = rdp(path, 0.008 * diag)
            carries.append({"object": obj.label, "track": obj.id, "a": a, "b": b, "grasp": g, "release": r,
                            "from": p0, "to": p1, "path": path.round(1).tolist(), "held_frac": round(frac, 2)})
    carries.sort(key=lambda k: k["a"])
    for k in carries:  # what it was put into or onto
        k["onto"] = next((o.label for o in tracks.objects() if o.label != k["object"] and inside(o, k["b"] + int(0.3 * fps), k["to"]["c"])), None)
    return {"steps": to_steps(carries, calib, fps), "carries": carries, "hand_seen": any_hand,
            "calibration": calib.to_json()}


def _pose_m(calib: Calibration, p: dict) -> dict:
    yaw = None if p["round"] else round(calib.angle(p["c"], p["yaw"]), 1)
    return {"px": p["c"], "m": calib.point(p["c"]), "yaw": yaw, "sym": p["sym"],
            "size_m": [round(calib.metres(p["c"], s), 4) for s in p["size"]]}


def to_steps(carries: list[dict], calib: Calibration, fps: float) -> list[dict]:
    """Turn carries into numbered pick / move / place steps in robot metres, each with its text."""
    steps = []
    for k in carries:
        a, b = _pose_m(calib, k["from"]), _pose_m(calib, k["to"])
        dist = math.dist(a["m"], b["m"])
        sym = k["from"]["sym"]
        turn = None if a["yaw"] is None or b["yaw"] is None else round(((b["yaw"] - a["yaw"]) + sym / 2) % sym - sym / 2, 1)
        base = {"object": k["object"]}
        steps.append({**base, "kind": "pick", "t": round(k["a"] / fps, 2), "t_grasp": round(k["grasp"] / fps, 2), **a})
        steps.append({**base, "kind": "move", "t0": round(k["a"] / fps, 2), "t1": round(k["b"] / fps, 2),
                      "path_px": k["path"], "path_m": [calib.point(p) for p in k["path"]],
                      "distance_m": round(dist, 3), "turn_deg": turn})
        steps.append({**base, "kind": "place", "t": round(k["b"] / fps, 2), "t_release": round(k["release"] / fps, 2),
                      "onto": k["onto"], **b})
    for i, s in enumerate(steps):
        s["id"] = i + 1
        s["text"] = describe_step(s)
    return steps


def describe_step(s: dict) -> str:
    """A short plain-English sentence for one step."""
    if s["kind"] == "pick":
        return f"Pick up the {s['object']}"
    if s["kind"] == "move":
        turn = f", turning it {abs(s['turn_deg']):.0f}°" if s.get("turn_deg") and abs(s["turn_deg"]) >= 8 else ""
        return f"Carry it {s['distance_m'] * 100:.0f} cm{turn}"
    return f"Put it in the {s['onto']}" if s.get("onto") else "Set it down"


def score(result: dict, truth: dict, calib: Calibration) -> dict:
    """Detected carries vs a synthetic clip's ground truth: timing error and position error in mm."""
    out = []
    picks = [s for s in result["steps"] if s["kind"] == "pick"]
    places = [s for s in result["steps"] if s["kind"] == "place"]
    for c in truth["carries"]:
        pk = next((p for p in picks if p["object"] == c["object"]), None)
        pl = next((p for p in places if p["object"] == c["object"]), None)
        if not pk or not pl:
            out.append({"object": c["object"], "found": False})
            continue
        f, t = calib.point(c["from_px"]), calib.point(c["to_px"])
        out.append({"object": c["object"], "found": True,
                    "pick_ms": round(abs(pk["t"] - c["t_pick"]) * 1000), "place_ms": round(abs(pl["t"] - c["t_place"]) * 1000),
                    "pick_mm": round(math.dist(pk["m"], f) * 1000, 1), "place_mm": round(math.dist(pl["m"], t) * 1000, 1),
                    "onto_ok": pl.get("onto") == c.get("into")})
    found = [o for o in out if o["found"]]
    return {"carries": out, "found": len(found), "expected": len(truth["carries"]),
            "extra": len(picks) - len(found),
            "worst_mm": max((max(o["pick_mm"], o["place_mm"]) for o in found), default=None),
            "worst_ms": max((max(o["pick_ms"], o["place_ms"]) for o in found), default=None)}
