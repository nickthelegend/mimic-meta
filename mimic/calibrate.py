"""Clip pixels -> robot table coordinates.

The demonstration is filmed from above, on the arm's mat, with the arm's base at the
bottom edge of the picture: you do the task from where the robot will stand. A
homography maps the four mat corners seen in the clip to their place in the robot
frame (metres; x right, y forward, origin under the base axis; see kinematics.py).

The default mat is 24 x 13.5 cm (16:9, so a landscape phone clip framed on it needs no
clicks), starting 17.5 cm in front of the base: the SO-101's comfortable reach with the
gripper pointing down.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

MAT_W, MAT_H, MAT_NEAR = 0.24, 0.135, 0.175
MAT = np.array([[-MAT_W / 2, MAT_NEAR + MAT_H], [MAT_W / 2, MAT_NEAR + MAT_H],
                [MAT_W / 2, MAT_NEAR], [-MAT_W / 2, MAT_NEAR]], np.float32)  # far-left, far-right, near-right, near-left


@dataclass
class Calibration:
    H: np.ndarray  # 3x3, clip pixels -> robot metres
    corners: list[list[float]]  # the four image points used, same order as MAT

    @staticmethod
    def default(width: int, height: int) -> "Calibration":
        return Calibration.from_corners([[0, 0], [width, 0], [width, height], [0, height]])

    @staticmethod
    def from_corners(corners) -> "Calibration":
        src = np.array(corners, np.float32).reshape(4, 2)
        return Calibration(cv2.getPerspectiveTransform(src, MAT), src.round(1).tolist())

    def to_table(self, uv) -> np.ndarray:
        p = np.array(uv, float).reshape(-1, 1, 2)
        return cv2.perspectiveTransform(p, self.H).reshape(-1, 2)

    def point(self, uv) -> list[float]:
        x, y = self.to_table([uv])[0]
        return [round(float(x), 4), round(float(y), 4)]

    def angle(self, uv, yaw_img: float) -> float:
        """An on-screen direction (degrees CCW, as seen) at pixel uv -> degrees CCW in the robot frame."""
        a = math.radians(yaw_img)
        p0, p1 = self.to_table([uv, [uv[0] + 10 * math.cos(a), uv[1] - 10 * math.sin(a)]])
        return math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))

    def metres(self, uv, px: float) -> float:
        """Rough length in metres of px pixels at uv (average of the two axes)."""
        p0, px_, py_ = self.to_table([uv, [uv[0] + px, uv[1]], [uv[0], uv[1] + px]])
        return float((np.linalg.norm(px_ - p0) + np.linalg.norm(py_ - p0)) / 2)

    def to_json(self) -> dict:
        return {"corners": self.corners, "mat": MAT.round(4).tolist(),
                "mat_size_m": [MAT_W, MAT_H], "mat_near_m": MAT_NEAR}
