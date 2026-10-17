"""Steps -> a robot program (see program.py for the format).

  RuleWriter       offline and deterministic: the same nine-waypoint pattern for every carry
  MuseSparkWriter  Muse Spark on the Meta Model API (OpenAI-compatible) reads the steps and
                   the key frames, writes the program, and repairs it when the safety check
                   finds problems. Falls back to the rules if the API is unreachable.

Both go through program.compile(), so Muse Spark never sets a joint angle and nothing it
writes reaches an arm without passing the same checks.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re

import httpx

from . import program as P

log = logging.getLogger("mimic.writer")

APPROACH_Z = 0.07  # m: travel height over the table
DEFAULT_HEIGHT = 0.03


def grasp_z(height: float) -> float:
    return round(min(max(height * 0.5, 0.008), 0.03), 4)


def closing_yaw(step: dict) -> float | None:
    """Jaws close across an object's short side: its long axis plus 90 degrees."""
    return None if step.get("yaw") is None else round((step["yaw"] + 90 + 90) % 180 - 90, 1)


def carries(steps: list[dict]) -> list[tuple[dict, dict, dict]]:
    out, i = [], 0
    while i + 2 < len(steps):
        a, b, c = steps[i:i + 3]
        if (a["kind"], b["kind"], c["kind"]) == ("pick", "move", "place"):
            out.append((a, b, c))
            i += 3
        else:
            i += 1
    return out


def summarize(steps: list[dict]) -> str:
    parts = []
    for pick, move, place in carries(steps):
        where = f"in the {place['onto']}" if place.get("onto") else f"{move['distance_m'] * 100:.0f} cm away"
        turn = f", turned {abs(move['turn_deg']):.0f}°" if move.get("turn_deg") and abs(move["turn_deg"]) >= 8 else ""
        parts.append(f"put the {pick['object']} {where}{turn}")
    if not parts:
        return "Nothing was picked up in this clip."
    s = ", then ".join(parts)
    return s[0].upper() + s[1:] + "."


class RuleWriter:
    name = "rules"

    def write(self, steps: list[dict], heights: dict | None = None, **_) -> dict:
        heights = heights or {}
        wps = []
        objects = {}
        for pick, move, place in carries(steps):
            obj = pick["object"]
            h = heights.get(obj, DEFAULT_HEIGHT)
            objects[obj] = {"height_m": h}
            onto_h = heights.get(place.get("onto"), 0.0) * 0.25 if place.get("onto") else 0.0
            gz, pz = grasp_z(h), round(grasp_z(h) + onto_h, 4)
            y0, y1 = closing_yaw(pick), closing_yaw(place)
            width = pick["size_m"][1] if pick.get("size_m") else None
            sid = pick["id"]
            (px, py), (qx, qy) = pick["m"], place["m"]
            wps += [
                {"label": f"above the {obj}", "step": sid, "xyz": [px, py, APPROACH_Z], "yaw": y0, "grip": "open"},
                {"label": f"down to the {obj}", "step": sid, "xyz": [px, py, gz], "yaw": y0, "grip": "open", "speed": 0.5},
                {"label": f"grip the {obj}", "step": sid, "xyz": [px, py, gz], "yaw": y0, "grip": "close", "object": obj,
                 "width_m": width, "dwell": 0.3},
                {"label": f"lift the {obj}", "step": sid, "xyz": [px, py, APPROACH_Z], "yaw": y0, "grip": "hold", "speed": 0.6},
            ]
            inner = move.get("path_m", [])[1:-1]
            for k, (x, y) in enumerate(inner):
                u = (k + 1) / (len(inner) + 1)
                yaw = None if y0 is None or y1 is None else round(y0 + (((y1 - y0) + 90) % 180 - 90) * u, 1)
                wps.append({"label": f"carry the {obj}", "step": move["id"], "xyz": [x, y, APPROACH_Z], "yaw": yaw, "grip": "hold"})
            target = f"the {place['onto']}" if place.get("onto") else "its new spot"
            wps += [
                {"label": f"over {target}", "step": place["id"], "xyz": [qx, qy, APPROACH_Z], "yaw": y1, "grip": "hold"},
                {"label": f"lower into {target}" if place.get("onto") else "set it down", "step": place["id"],
                 "xyz": [qx, qy, pz], "yaw": y1, "grip": "hold", "speed": 0.5},
                {"label": f"let go of the {obj}", "step": place["id"], "xyz": [qx, qy, pz], "yaw": y1, "grip": "open",
                 "object": obj, "dwell": 0.3},
                {"label": "back up", "step": place["id"], "xyz": [qx, qy, APPROACH_Z], "yaw": y1, "grip": "open", "speed": 0.8},
            ]
        return {"summary": summarize(steps), "objects": objects, "waypoints": wps, "writer": self.name}


SYSTEM = """You are the motion planner of MIMIC. A person filmed themselves doing a tabletop task; \
vision models turned the clip into pick / move / place steps with positions already converted to the \
robot's table frame. Write the program a small 6-joint arm (SO-101 class, parallel gripper) runs to \
repeat the task.

Frame: metres. x = robot's right, y = straight ahead, z = up from the table. The base is at (0, 0). \
It reaches 0.17-0.32 m from the base, |angle| < 85 deg from straight ahead.
Waypoints give the fingertip position only; deterministic code solves joint angles, replays the \
program in simulation and rejects anything unsafe. Rules:
- travel between objects at z = 0.07; descend and lift vertically; descend at speed 0.5
- grip "close" needs "object" and "width_m" (the object's short side); dwell 0.3 s on close and open
- grasp height = half the object's height (between 0.008 and 0.03 m); estimate heights from the \
object names and key frames when you can (a cup is taller than a coin)
- "yaw" is the direction the jaws close in, degrees CCW from +x seen from above: the object's \
long-axis yaw + 90; null for round objects
- keep every step's id in "step"; give each waypoint a short plain-English "label"
- write a one-sentence "summary" of the task as the person would say it, and list any doubts in "notes"
Reply with JSON only, matching the schema."""


class MuseSparkWriter:
    name = "muse-spark"

    def __init__(self, base: str | None = None, key: str | None = None, model: str | None = None,
                 transport: httpx.BaseTransport | None = None, rounds: int = 2, timeout: float = 90):
        self.base = (base or os.getenv("MUSE_API_BASE", "https://api.meta.ai/v1")).rstrip("/")
        self.key = key or os.getenv("MUSE_API_KEY") or os.getenv("META_API_KEY")
        self.model = model or os.getenv("MUSE_MODEL", "muse-spark-1.3")
        self.transport, self.rounds, self.timeout = transport, rounds, timeout

    @staticmethod
    def configured() -> bool:
        return bool(os.getenv("MUSE_API_KEY") or os.getenv("META_API_KEY"))

    def _chat(self, messages: list[dict]) -> str:
        body = {"model": self.model, "messages": messages, "temperature": 0.2,
                "response_format": {"type": "json_schema", "json_schema": {"name": "mimic_program", "schema": P.PROGRAM_SCHEMA}}}
        with httpx.Client(transport=self.transport, timeout=self.timeout) as c:
            r = c.post(f"{self.base}/chat/completions", json=body, headers={"Authorization": f"Bearer {self.key}"})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _json(text: str) -> dict:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise ValueError("no JSON object in the reply")
        return json.loads(m.group(0))

    def write(self, steps: list[dict], heights: dict | None = None, frames: list[bytes] | None = None,
              objects_at: dict | None = None) -> dict:
        if not self.key:
            raise RuntimeError("MUSE_API_KEY is not set")
        lean = [{k: v for k, v in s.items() if k not in ("path_px", "px")} for s in steps]
        content = [{"type": "text", "text": "Steps from the clip:\n" + json.dumps(lean)}]
        for jpg in (frames or [])[:4]:  # key frames: start, each pick, the end
            content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpg).decode()}})
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}]
        trace = []
        prog = None
        for rnd in range(self.rounds + 1):
            reply = self._chat(messages)
            prog = self._json(reply)
            prog["writer"] = self.name
            checked = P.compile(prog, objects_at)
            trace.append({"round": rnd + 1, "issues": checked["issues"]})
            if checked["ok"] or rnd == self.rounds:
                break
            # the safety check found problems: hand them back and ask for a fixed program
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": "The safety check rejected that program:\n" + json.dumps(checked["issues"]) +
                          "\nFix those waypoints and reply with the whole program again."}]
        prog["trace"] = trace
        prog["model"] = self.model
        return prog


def get_writer(name: str | None):
    """Rules unless Muse Spark is asked for by name (it's a paid API: never the silent default)."""
    name = (name or os.getenv("MIMIC_WRITER") or "rules").lower()
    return MuseSparkWriter() if name in ("muse", "muse-spark", "muse_spark") else RuleWriter()
