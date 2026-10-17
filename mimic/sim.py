"""Replay a compiled program on a simulated arm, sample by sample, exactly the way the
real arms move (arm.Arm.move: each joint steps toward its target at no more than
VMAX * speed, 25 times a second). The samples drive the safety check and the 3-D replay."""

from __future__ import annotations

import numpy as np

from .kinematics import HOME, RATE, VMAX, elbow_point, fk


def simulate(waypoints: list[dict], start=None, rate: float = RATE) -> list[dict]:
    q = np.array(start if start is not None else HOME, float)
    dt = 1 / rate
    t = 0.0
    out = [{"t": 0.0, "q": q.round(2).tolist(), "w": -1}]
    for k, w in enumerate(waypoints):
        target = np.array(w["q"], float)
        lim = VMAX * w.get("speed", 1.0) * dt
        for _ in range(int(60 * rate)):  # a minute per move at most
            d = target - q
            if np.all(np.abs(d) < 0.05):
                break
            q = q + np.clip(d, -lim, lim)
            t += dt
            out.append({"t": round(t, 3), "q": q.round(2).tolist(), "w": k})
        for _ in range(int(round(w.get("dwell", 0) * rate))):
            t += dt
            out.append({"t": round(t, 3), "q": q.round(2).tolist(), "w": k})
    return out


def attach(samples: list[dict], waypoints: list[dict], objects: dict) -> dict:
    """Which object the gripper holds at every sample, and where each object ends up.
    objects: label -> [x, y] on the table at the start."""
    pos = {k: list(v) for k, v in objects.items()}
    held = None
    for s in samples:
        w = waypoints[s["w"]] if s["w"] >= 0 else {}
        tip = fk(s["q"])
        if held:
            pos[held] = [round(float(tip[0]), 4), round(float(tip[1]), 4)]
        if w.get("grip") == "close" and w.get("object") and held is None and s["q"][5] <= w["q"][5] + 0.5:
            held = w["object"]
        elif w.get("grip") == "open" and held and s["q"][5] >= w["q"][5] - 0.5:
            held = None
        s["held"] = held
    return pos


def lowest(samples: list[dict]) -> tuple[float, float]:
    """Lowest fingertip and elbow heights over the whole replay (metres)."""
    tips = min(float(fk(s["q"])[2]) for s in samples)
    elbows = min(float(elbow_point(s["q"])[2]) for s in samples)
    return tips, elbows
