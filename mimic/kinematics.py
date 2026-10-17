"""SO-101 / Thenar arm kinematics, in the same joint convention as REACH (reach/arm.py):

    q = [base_pan, shoulder, elbow, wrist_flex, wrist_roll, gripper]   (degrees)

Shoulder is measured from vertical (+ = leans forward), elbow and wrist flex fold
forward (+). The robot frame is metres on the table: x to the robot's right, y
straight out in front of it, z up, origin on the table under the base axis.
The link lengths are the ones REACH's 3-D view draws (web/index.html).
"""

from __future__ import annotations

import math

import numpy as np

H0, L1, L2, L3 = 0.10, 0.116, 0.135, 0.10  # shoulder height, upper arm, forearm, wrist-to-fingertip

LO = np.array([-85, -80, -80, -80, -85, 0], float)
HI = np.array([85, 80, 80, 80, 85, 70], float)
HOME = np.array([0, -25, 35, 0, 0, 20], float)
VMAX = np.array([60, 40, 50, 80, 90, 120], float)  # deg/s per joint, as REACH
RATE = 25.0
JOINTS = ["base", "shoulder", "elbow", "wrist_flex", "wrist_roll", "gripper"]

GRIP_OPEN = 60.0
GRIP_CLOSED = 8.0  # REACH's "closed on the item"


class Unreachable(ValueError):
    pass


def fk(q) -> np.ndarray:
    """Fingertip position (x, y, z) in metres for joint angles q (degrees)."""
    t0, t1, t2, t3 = (math.radians(v) for v in q[:4])
    a1, a2 = t1, t1 + t2
    a3 = a2 + t3
    r = L1 * math.sin(a1) + L2 * math.sin(a2) + L3 * math.sin(a3)
    z = H0 + L1 * math.cos(a1) + L2 * math.cos(a2) + L3 * math.cos(a3)
    return np.array([r * math.sin(t0), r * math.cos(t0), z])


def elbow_point(q) -> np.ndarray:
    t0, t1, t2 = (math.radians(v) for v in q[:3])
    r = L1 * math.sin(t1) + L2 * math.sin(t1 + t2)
    z = H0 + L1 * math.cos(t1) + L2 * math.cos(t1 + t2)
    return np.array([r * math.sin(t0), r * math.cos(t0), z])


PITCHES = (180, 170, 160, 150, 140, 130, 120, 190, 200)  # gripper angle from vertical-up; 180 = straight down


def _ik_pitch(x, y, z, phi, yaw, grip):
    t0 = math.degrees(math.atan2(x, y))
    r = math.hypot(x, y)
    p = math.radians(phi)
    dx, dz = r - L3 * math.sin(p), z - L3 * math.cos(p) - H0  # wrist centre relative to the shoulder
    d = (dx * dx + dz * dz - L1 * L1 - L2 * L2) / (2 * L1 * L2)
    if abs(d) > 1:
        return None, "out of the arm's reach"
    t2 = math.acos(d)  # elbow folds forward
    a1 = math.atan2(dx, dz) - math.atan2(L2 * math.sin(t2), L1 + L2 * math.cos(t2))
    t1, t2 = math.degrees(a1), math.degrees(t2)
    t3 = phi - t1 - t2
    # with roll 0 the jaws close across the reach direction (along -t0 from +x); roll turns them CCW
    roll = 0.0 if yaw is None else float(np.clip(((yaw + t0) + 90) % 180 - 90, LO[4], HI[4]))
    q = np.array([t0, t1, t2, t3, roll, grip])
    bad = [JOINTS[i] for i in range(5) if not (LO[i] - 1e-6 <= q[i] <= HI[i] + 1e-6)]
    return (None, f"needs {', '.join(bad)} past its limit") if bad else (q, "")


def ik(xyz, yaw: float | None = None, grip: float = GRIP_OPEN) -> np.ndarray:
    """Joint angles that put the fingertip at xyz, gripper as close to pointing straight down
    as the joint limits allow (tilting toward the robot up to 60 deg when the point is near or
    far). yaw is the direction the jaws close in, degrees CCW from +x seen from above (None =
    don't care); the wrist roll is folded into +-90, since a parallel gripper is symmetric.
    Raises Unreachable if no tilt works."""
    x, y, z = (float(v) for v in xyz)
    why = ""
    for phi in PITCHES:
        q, why = _ik_pitch(x, y, z, phi, yaw, grip)
        if q is not None:
            return q
    raise Unreachable(f"({x:.3f}, {y:.3f}, {z:.3f}) m {why}")


def reachable(xyz) -> bool:
    try:
        ik(xyz)
        return True
    except Unreachable:
        return False
