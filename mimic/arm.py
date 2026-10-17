"""Robot backends, trimmed from REACH (../reach-amazon/reach/arm.py) so a MIMIC program
drives the same arms the same way. Every robot takes the six-number pose

    [base_pan, shoulder, elbow, wrist_flex, wrist_roll, gripper]

in its own calibrated degrees. Motion is streamed as small interpolated steps (25 Hz)
capped per joint, so nothing jumps.

  SimArm     no hardware; what the tests and the web page's "run on arm" use by default
  SO101Arm   a bench SO-101 / Thenar follower over USB serial ("Q a b c d e f", "ARM", "STOP")
"""

from __future__ import annotations

import asyncio
import logging
import time

import numpy as np

from .kinematics import HI, HOME, LO, JOINTS, RATE, VMAX

log = logging.getLogger("mimic.arm")


class Stopped(Exception):
    """The robot was stopped (from the web page, or a fault)."""


class Arm:
    name = "arm"
    speedup = 1.0  # tests run the simulator faster than real time

    def __init__(self):
        self.lo, self.hi = LO.copy(), HI.copy()
        self.q = HOME.copy()
        self.target = HOME.copy()
        self.stop_flag = asyncio.Event()

    def clamp(self, q) -> np.ndarray:
        return np.clip(np.asarray(q, float), self.lo, self.hi)

    async def connect(self) -> None:
        pass

    async def _write(self, q: np.ndarray) -> None:
        raise NotImplementedError

    def _check(self) -> None:
        if self.stop_flag.is_set():
            raise Stopped()

    async def move(self, target, speed: float = 1.0) -> None:
        """Interpolate to target at <= VMAX*speed per joint. Raises Stopped."""
        target = self.clamp(target)
        self.target = target
        dt = 1 / RATE
        while True:
            self._check()
            d = target - self.q
            lim = VMAX * speed * self.speedup * dt
            self.q = self.q + np.clip(d, -lim, lim)
            await self._write(self.q)
            if np.all(np.abs(d) < 0.05):
                return
            await asyncio.sleep(dt)

    async def stop(self) -> None:
        self.stop_flag.set()

    def clear_stop(self) -> None:
        self.stop_flag.clear()

    def state(self) -> dict:
        return {"backend": self.name, "joints": dict(zip(JOINTS, np.round(self.q, 1).tolist())),
                "lo": self.lo.round(1).tolist(), "hi": self.hi.round(1).tolist()}


class SimArm(Arm):
    name = "sim"

    async def _write(self, q):
        return


class SO101Arm(Arm):
    """A bench SO-101 follower on USB. Refuses to arm unless it acknowledges STOP first,
    and every streamed pose passes the table guard from thenar-arms when it is present."""

    name = "so101"

    def __init__(self, port: str, guard=None):
        super().__init__()
        self.port = port
        self.guard = guard
        self.ser = None

    async def connect(self) -> None:
        import serial

        self.ser = serial.Serial(self.port, 115200, timeout=0.02, write_timeout=0.1)
        await asyncio.sleep(2)
        self.ser.reset_input_buffer()
        self.ser.write(b"STOP\n")
        if not await self._expect("STOP", 2.0):
            raise RuntimeError("follower did not acknowledge STOP; refusing to arm")
        await self._write(HOME)
        self.ser.write(b"ARM\n")
        if not await self._expect("ARMED", 3.0):
            raise RuntimeError("follower did not arm")
        self.q = HOME.copy()
        log.info("SO-101 armed on %s", self.port)

    async def _expect(self, word: str, timeout: float) -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            line = self.ser.readline(256).decode(errors="replace").strip()
            if line.startswith("FAULT"):
                raise RuntimeError(line)
            if line.startswith(word):
                return True
            await asyncio.sleep(0.01)
        return False

    async def _write(self, q):
        if self.guard and not self.guard.safe(q):
            await self.stop()
            raise Stopped("pose would enter the table")
        self.ser.write(("Q " + " ".join(f"{v:.3f}" for v in q) + "\n").encode())
        reply = self.ser.readline(256).decode(errors="replace").strip()
        if reply.startswith(("FAULT", "STOP")):
            self.stop_flag.set()
            raise Stopped(reply)

    async def stop(self) -> None:
        await super().stop()
        if self.ser:
            self.ser.write(b"STOP\n")


def load_guard(thenar_arms_dir: str | None):
    """The SO-101 table guard from the thenar-arms repo, if it's on this machine."""
    if not thenar_arms_dir:
        return None
    import importlib.util
    from pathlib import Path

    p = Path(thenar_arms_dir) / "so101-mg996r/firmware/bridge.py"
    if not p.exists():
        return None
    spec = importlib.util.spec_from_file_location("thenar_bridge", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.TableGuard()


async def replay(program: dict, arm: Arm, speed: float = 1.0, on_step=None) -> None:
    """Drive any arm through a compiled program's waypoints (q already solved and checked)."""
    if not program.get("ok"):
        raise ValueError("program has unresolved issues; refusing to run it on an arm")
    for i, w in enumerate(program["waypoints"]):
        if on_step:
            on_step(i, w)
        await arm.move(w["q"], speed * w.get("speed", 1.0))
        if w.get("dwell"):
            await asyncio.sleep(w["dwell"] / arm.speedup)
