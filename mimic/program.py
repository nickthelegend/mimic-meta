"""The robot program: what a writer (rules or Muse Spark) produces, and the deterministic
code that turns it into joint angles and refuses it if it isn't safe.

A writer only says *where the fingertip goes* in task space, never joint angles:

    {"summary": "Put the red block in the blue bowl, then ...",
     "objects": {"red block": {"height_m": 0.03}},
     "waypoints": [
        {"label": "above the red block", "step": 1, "xyz": [-0.045, 0.253, 0.07],
         "yaw": 110.0, "grip": "open", "speed": 1.0},
        {"label": "grip the red block", "step": 1, "xyz": [-0.045, 0.253, 0.015],
         "grip": "close", "object": "red block", "width_m": 0.015, "dwell": 0.3},
        ...]}

xyz is metres in the robot frame (x right, y forward, z up from the table), yaw is the
direction the jaws close in, degrees counter-clockwise from +x seen from above (null =
any), grip is "open" | "close" | "hold". compile() solves every waypoint with the arm's
inverse kinematics, replays the result on the simulated arm, and checks it the way
HOTARU's gesture compiler does: every pose inside the joint limits, every step between
poses above the table. A program with issues is still shown, but never sent to an arm.
"""

from __future__ import annotations

import copy

import numpy as np

from . import sim
from .kinematics import GRIP_OPEN, HOME, JOINTS, Unreachable, ik

SCHEMA_VERSION = 1
TABLE_CLEARANCE = 0.004  # m: the fingertip may touch down to this height, never below
ELBOW_CLEARANCE = 0.03
MAX_WAYPOINTS = 200
MAX_REACH_M = 0.40
JAW_DEG_PER_M = 70 / 0.08  # gripper degrees per metre of opening (70 deg ~ 8 cm)

WAYPOINT_SCHEMA = {
    "type": "object",
    "required": ["label", "xyz", "grip"],
    "properties": {
        "label": {"type": "string"}, "step": {"type": "integer"},
        "xyz": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
        "yaw": {"type": ["number", "null"]}, "grip": {"enum": ["open", "close", "hold"]},
        "object": {"type": ["string", "null"]}, "width_m": {"type": ["number", "null"]},
        "dwell": {"type": "number"}, "speed": {"type": "number"},
    },
}
PROGRAM_SCHEMA = {
    "type": "object",
    "required": ["summary", "waypoints"],
    "properties": {
        "summary": {"type": "string"},
        "objects": {"type": "object", "additionalProperties": {"type": "object", "properties": {"height_m": {"type": "number"}}}},
        "notes": {"type": "array", "items": {"type": "string"}},
        "waypoints": {"type": "array", "items": WAYPOINT_SCHEMA},
    },
}


def closed_deg(width_m: float | None) -> float:
    """Gripper command that just squeezes an object of this width."""
    if not width_m:
        return 8.0
    return float(np.clip(width_m * JAW_DEG_PER_M - 5, 0, GRIP_OPEN))


def compile(program: dict, objects_at: dict | None = None) -> dict:
    """Solve, replay and check a written program. Returns a copy with q on every waypoint,
    "issues", "ok", "duration_s", the replay "samples" and where each object ends up."""
    p = copy.deepcopy(program)
    p.setdefault("mimic", SCHEMA_VERSION)
    p.setdefault("robot", "so101")
    p["joints"] = JOINTS
    p["units"] = {"xyz": "m", "yaw": "deg", "q": "deg", "t": "s"}
    issues: list[dict] = []
    wps = p.get("waypoints") or []
    if not isinstance(wps, list) or not wps:
        issues.append({"waypoint": None, "issue": "the program has no waypoints"})
        wps = []
    if len(wps) > MAX_WAYPOINTS:
        issues.append({"waypoint": None, "issue": f"{len(wps)} waypoints is more than {MAX_WAYPOINTS}"})
        wps = wps[:MAX_WAYPOINTS]
    grip = float(HOME[5])
    solved = []
    written = []  # every waypoint as written, solvable or not, so an edit never loses one
    for i, w in enumerate(wps):
        w = dict(w) if isinstance(w, dict) else {"label": f"waypoint {i + 1}"}
        w.setdefault("label", f"waypoint {i + 1}")
        written.append(dict(w))
        w["speed"] = float(np.clip(w.get("speed", 1.0) or 1.0, 0.1, 1.0))
        w["dwell"] = float(np.clip(w.get("dwell", 0.0) or 0.0, 0.0, 5.0))
        if w.get("grip") not in ("open", "close", "hold"):
            issues.append({"waypoint": i, "issue": f"grip must be open, close or hold, not {w.get('grip')!r}"})
            w["grip"] = "hold"
        if w["grip"] == "open":
            grip = GRIP_OPEN
        elif w["grip"] == "close":
            grip = closed_deg(w.get("width_m"))
        try:
            xyz = [float(v) for v in w["xyz"]]
            if len(xyz) != 3:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            issues.append({"waypoint": i, "issue": "xyz must be three numbers in metres"})
            continue
        if max(abs(xyz[0]), abs(xyz[1])) > MAX_REACH_M or not (-0.05 < xyz[2] < 0.5):
            issues.append({"waypoint": i, "issue": f"xyz {xyz} is not on this table (metres?)"})
            continue
        if xyz[2] < TABLE_CLEARANCE:
            issues.append({"waypoint": i, "issue": f"fingertip at z={xyz[2]:.3f} m would press into the table"})
            xyz[2] = TABLE_CLEARANCE
        try:
            q = ik(xyz, w.get("yaw") if w.get("yaw") is not None else None, grip)
        except Unreachable as e:
            issues.append({"waypoint": i, "issue": str(e)})
            continue
        w["xyz"] = [round(v, 4) for v in xyz]
        w["q"] = q.round(2).tolist()
        w["src"] = i  # index in the written program
        written[-1]["xyz"] = w["xyz"]
        solved.append(w)
    home = {"label": "home", "pose": "home", "grip": "hold", "q": HOME.round(2).tolist(), "speed": 1.0, "dwell": 0.0, "src": None}
    full = solved + [home] if solved else []
    samples = sim.simulate(full) if full else []
    if samples:
        tip, elbow = sim.lowest(samples)
        if tip < TABLE_CLEARANCE - 1e-3:
            issues.append({"waypoint": None, "issue": f"between waypoints the fingertip dips to {tip * 1000:.0f} mm, below the table"})
        if elbow < ELBOW_CLEARANCE:
            issues.append({"waypoint": None, "issue": f"the elbow comes within {elbow * 1000:.0f} mm of the table"})
    final = sim.attach(samples, full, objects_at or {}) if samples else {}
    p["waypoints"] = full
    p["written"] = written
    p["issues"] = issues
    p["ok"] = not issues and bool(solved)
    p["duration_s"] = samples[-1]["t"] if samples else 0.0
    p["samples"] = samples
    p["objects_end"] = final
    return p


def strip(p: dict) -> dict:
    """The program as the user sees and edits it: no solved angles or replay samples."""
    keep = {k: v for k, v in p.items() if k not in ("samples", "objects_end", "joints", "units", "issues", "ok", "duration_s", "written")}
    keep["waypoints"] = [{k: v for k, v in w.items() if k not in ("q", "src")} for w in p.get("written", [])]
    return keep
