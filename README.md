# MIMIC

Live demo: https://mimic-meta.201-18-198-162.sslip.io/

**Film yourself doing a task on your phone. MIMIC tracks your hand and the objects, notates the steps, writes a checked robot program, and a printable arm does it.**

Built for the [Meta Global AI Developer Hackathon](https://dev.meta.ai/events/global-hackathon) (Indie track, "Push the Frontier": robotics) by ThenarLabs. The hardware is the printable SO-101 / Thenar arm.

```
phone clip ─▶ hand + object tracks ─▶ pick / move / place steps ─▶ waypoint program ─▶ IK + safety check ─▶ replay on the arm
              SAM 3.1                 mimic/segment.py              Muse Spark           mimic/program.py     sim or SO-101
              (OpenCV stand-in)                                     (or offline rules)
```

| | |
|---|---|
| Research: rules, dates, SAM 3.1 and Muse Spark access, prior art | [RESEARCH.md](RESEARCH.md) |
| Application draft (you submit it) | [APPLICATION.md](APPLICATION.md) |
| Product record for design work | [PRODUCT.md](PRODUCT.md) |

## Run it

```bash
uv venv -p 3.12 .venv
```

```
Using CPython 3.12.12
Creating virtual environment at: .venv
```

```bash
uv pip install -p .venv/bin/python -r requirements.txt
```

uv lists about 30 packages, each as `+ name==version`, ending around `+ websockets==…`. A second run prints `Checked 8 packages`.

```bash
.venv/bin/uvicorn server:app --port 8730
```

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8730 (Press CTRL+C to quit)
```

If another server already holds the port, uvicorn prints `[Errno 48] error while attempting to bind on address ('127.0.0.1', 8730): address already in use` and exits. Stop that server or pass a different `--port`.

Check it from a second shell:

```bash
curl -s http://localhost:8730/api/health
```

```
{"ok":true,"trackers":{"color":true,"mediapipe":false,"sam3":false},"writers":{"rules":true,"muse-spark":false},"arm":"sim"}
```

`mediapipe` turns `true` once it's installed and `models/hand_landmarker.task` is in place. `muse-spark` and `sam3` turn `true` when `META_API_KEY` is set.

Open <http://localhost:8730>. On a first visit (nothing reviewed yet) the page loads the synthetic sample clip by itself (about 9 s the first time, since it generates `samples/sample.mp4` and tracks it; `/?sample` forces it). It then shows everything: the tracked overlay on the clip, the movement score, the steps with their measured error against ground truth, the program, and the 3-D replay. Press **Play** to run the clip and the arm together. Click a step to jump both to it, or drag on the score to scrub. Use **Upload a clip** for your own video.

Tests (offline; no network, no paid APIs):

```bash
.venv/bin/python -m pytest -q
```

```
................................                                         [100%]
32 passed, 1 warning in 35s
```

The one warning is Starlette's `StarletteDeprecationWarning` about `httpx` in its test client. It's harmless.

Run the pipeline from the command line. First make the synthetic sample clip. This writes `samples/sample.mp4` and `samples/sample.truth.json` and prints the ground truth:

```bash
.venv/bin/python -m mimic.synth samples/sample.mp4
```

```
{
 "fps": 30,
 "width": 960,
 "height": 540,
 "prompts": [
  "hand",
  "red block",
  "green block",
  "blue bowl"
 ],
 "carries": [
 …
 "heights": {
  "red block": 0.03,
  "green block": 0.025,
  "blue bowl": 0.04
 }
}
```

Then turn the clip into a checked program. It prints the steps, the check, the timings and, because the clip has a truth file, the score:

```bash
.venv/bin/python -m mimic.pipeline samples/sample.mp4
```

```
{
 "steps": [
  {
   "object": "red block",
   "kind": "pick",
 …
 "check": {
  "ok": true,
  "issues": [],
  "duration_s": 14.88,
  "waypoints": 17
 },
 …
 "score": {
  …
  "found": 2,
  "expected": 2,
  "extra": 0,
  "worst_mm": 1.9,
  "worst_ms": 100
 }
}
```

Add `--json` to print only the robot program (`summary`, `objects`, `waypoints`), or `--version` for `mimic 0.1.0`.

`ffmpeg` is optional. With it, generated and uploaded clips are re-encoded to H.264 so the browser can play them.

## How it works

| Module | Does |
|---|---|
| `mimic/tracks.py` | One `Tracker` interface: text prompts in ("hand", "red block"), per-frame outline, box, centroid and yaw out. `ColorTracker` (OpenCV: colour words and skin tone) is the offline stand-in; `MediaPipeTracker` adds real hand landmarks; `Sam3Tracker` calls SAM 3.1 on the Meta Model API, one concept per request. Clips are streamed at 640 px, thinned to 30 fps and capped at 120 s, so a long 4K phone clip never sits in memory. |
| `mimic/segment.py` | An object is *carried* when it moves a real distance with a hand on it. Speed hysteresis, a minimum duration and a net-displacement test mean the bowl wobbling under a hand isn't a carry. Each carry becomes pick / move / place, with position in mm, yaw, size, and what it was put into. `score()` compares the result with a synthetic clip's ground truth. |
| `mimic/calibrate.py` | A homography from clip pixels to the robot's table frame. The default mat is 24 × 13.5 cm, starting 17.5 cm in front of the base: where the SO-101 reaches with the gripper pointing down. |
| `mimic/writer.py` | `RuleWriter` (offline, the default) and `MuseSparkWriter` (`muse-spark-1.3`, OpenAI-compatible, JSON-schema output, steps plus key frames). Both write **fingertip waypoints only**. When the check rejects Muse Spark's program, the issues go back to it for up to two repair rounds. If the API fails, the rules take over and the page says so. |
| `mimic/program.py` | Compiles a written program: IK for every waypoint, replay in simulation, then refusal if any pose breaks a joint limit, the fingertip dips below the table between poses, or the elbow nears the table. The same discipline as HOTARU's gesture compiler. |
| `mimic/kinematics.py` | SO-101 / Thenar FK and IK in REACH's joint convention `[base, shoulder, elbow, wrist_flex, wrist_roll, gripper]` with REACH's link lengths and limits. The rest pose is a folded "ready" pose `[0, -10, 80, 60, 0, 20]` over the mat's near edge (REACH's taller `[0, -25, 35, 0]` suits its rover). The gripper tilts up to 60° when straight down won't reach. |
| `mimic/sim.py`, `mimic/arm.py` | The simulator steps exactly like REACH's `Arm.move` (25 Hz, per-joint speed caps); tests check that. `SimArm` and `SO101Arm` are REACH's backends, including the serial protocol and the STOP-before-ARM handshake. `replay()` refuses unchecked programs. |
| `mimic/synth.py` | The synthetic demonstration: a hand puts the red block in the blue bowl (turning it 25°), then slides the green block and turns it 45°. It has shadows, skin and sensor noise, and exact ground truth. |
| `server.py`, `web/index.html` | FastAPI app and the one-page review UI. Endpoints: `/api/analyze`, `/api/sample`, `/api/recheck/{run}` (edit the program and check it again), `/api/execute/{run}` (refused unless the check passes), `/api/stop`, `/api/arm`. |

On the sample clip, both carries are found, every pick and place lands within **1.9 mm** and **100 ms** of the ground truth, and no false carries are reported (`tests/test_mimic.py`).

### Configuration

| Env | Default | |
|---|---|---|
| `MIMIC_ARM` | `sim` | `so101` drives a real follower on `MIMIC_SO101_PORT` |
| `MIMIC_THENAR_ARMS` | — | path to the thenar-arms repo, to load its SO-101 table guard |
| `META_API_KEY` | — | Meta Model API key. It unlocks the Muse Spark writer and SAM 3.1 in the page's menus. **Both are paid and only used when picked;** the default stays offline. |
| `MUSE_MODEL` / `MIMIC_SAM_MODEL` | `muse-spark-1.3` / `sam-3.1` | |
| `MIMIC_WRITER` | `rules` | `muse-spark` makes it the default for the CLI |
| `MIMIC_HAND_MODEL` | `models/hand_landmarker.task` | for the MediaPipe tracker |

## TODO: what needs you

**Apply (by Oct 25, 11:59 PM ET; earlier is safer, since the cap can close it):**
- [ ] Fill the `[[ ]]` blanks in [APPLICATION.md](APPLICATION.md) and submit it on Cerebral Valley. Nothing has been submitted.
- [ ] Decide when this repo goes public (the Official Rules come out before Oct 26). Re-read them on the 26th for video length, repo and pre-existing-work rules.

**Keys and access (paid; I never ran them):**
- [ ] Create a Meta Model API key at dev.meta.ai and set `META_API_KEY`. Pick **Muse Spark** in the page's writer menu to try it. Use Standard mode, not Contributor, because Contributor lets Meta train on the clips.
- [ ] Send one real clip to SAM 3.1 (`tracker = SAM 3.1`). The raw reply is saved next to the clip as `*.sam-<prompt>.json`. Then wire `parse_reply()` in `mimic/tracks.py`: decode the special-token masks (Meta's `@meta-sam/parser` documents the format) into one outline polygon per object per frame. `from_masks()` already turns that into tracks, and it's tested.
- [ ] Optional: `pip install mediapipe` and put `hand_landmarker.task` in `models/` for real hand landmarks and pinch aperture.

**Filming:**
- [ ] Print a 24 × 13.5 cm mat with corner marks (the sample clip shows the look). Put the arm's base 17.5 cm from its near edge.
- [ ] Film from above (phone on a stand), landscape, framed on the mat, with the arm's side at the bottom of the picture. Use bright, solid-coloured objects until SAM 3.1 is wired in: the OpenCV stand-in finds objects by the colour word in their name.
- [ ] Record 10+ real clips of 3 tasks for the demo and the success-rate table.

**Hardware:**
- [ ] Run on the printed SO-101 / Thenar follower: `MIMIC_ARM=so101 MIMIC_SO101_PORT=/dev/tty.usbmodem… MIMIC_THENAR_ARMS=…`. Calibrate its joints to REACH's convention first.
- [ ] Measure a ruler-checked mat calibration, and the gripper's degrees-per-mm (`JAW_DEG_PER_M` in `mimic/program.py` is an estimate).
- [ ] Measure the success rate over 20 trials per task for the write-up.

**Known gaps (good hackathon-week work):**
- Calibration from the mat's printed corners (`Calibration.from_corners` exists, but nothing detects the corners).
- Object heights come from ground truth on the sample, and default to 3 cm otherwise; Muse Spark can estimate them from key frames.
- Replay is open-loop: if an object has moved since filming, the arm misses it.

## License

MIT. See [LICENSE](LICENSE).
