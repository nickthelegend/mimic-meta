# MIMIC: application draft

**For:** Meta Global AI Developer Hackathon. **Indie track**, theme **"Push the Frontier"** (robotics).
**Apply at:** <https://cerebralvalley.ai/e/meta-ai-developer-hackathon>, linked from <https://dev.meta.ai/events/global-hackathon>
**Deadline:** Oct 25, 2026, 11:59 PM ET (Oct 26, 9:29 AM IST), or earlier if 20,000 spots fill. **Apply early.**

> This is a draft for you to submit. Nothing has been sent. The real form questions sit behind a sign-in (see [RESEARCH.md](RESEARCH.md#how-applications-are-selected)), so the blocks below are written against the two published, equally weighted criteria: **project idea** (clear, feasible, fits a theme) and **technical skill** (a past AI project, what you built, the techniques). Paste each block into whichever question asks for it. Fill every `[[ ]]`, and delete anything you can't stand behind.

---

## One-liner (≤ 150 characters)

> Film yourself doing a task on your phone. SAM 3.1 tracks your hand, Muse Spark writes the robot program, and a printable arm (about $300) does it.

Shorter: *Show it once on your phone; a printable robot arm repeats it.*

## Track and theme

- **Track:** Indie developer
- **Theme:** Push the Frontier, robotics

## Project idea (the main description, ~250 words)

> **MIMIC turns one phone video of you doing a task into a program a printable robot arm (about $300) runs.**
>
> You film from above, on the arm's mat, doing something simple: put the red block in the bowl, slide the box over. **SAM 3.1** tracks your hand and each object by name ("hand", "red block", "blue bowl"), across the whole clip. MIMIC finds the moments that matter: when an object starts moving under your hand, where it goes, how it turns, and where you let go. That gives a list of pick / carry / place steps, in millimetres on the mat.
>
> **Muse Spark** reads those steps and key frames and writes the robot program as named fingertip waypoints: "above the red block", "grip it", "lower into the bowl". It never sets a joint angle. Deterministic code solves the arm's kinematics, replays the program in simulation at the arm's real step rate, and **refuses it** if any pose breaks a joint limit or touches the table. When it refuses, the issues go back to Muse Spark, which fixes the program. Only a checked program runs on the arm.
>
> The result is a readable, editable program, not opaque weights. One web page shows the clip with its tracking, a movement score (like dance notation) of what you did beside what the arm will do, the program, and a 3-D replay.
>
> Research systems that learn from human video (MimicPlay, OKAMI, Vid2Robot) need robot demos, depth cameras or big paired datasets. MIMIC needs a phone. It feeds ThenarLabs' paid-demonstration corpus: anyone with a phone can teach a robot, with no teleop rig.

## Why it fits "Push the Frontier"

> Robotics is named in the theme. The frontier is that "I showed my robot a video and it did the task" is still a research result (CoRL/RSS papers on lab rigs). MIMIC makes it a product anyone can use with a phone and a printed arm. It also leans on what is new in Meta's stack: SAM 3.1's text-prompted multi-object video tracking (16 objects per pass), and Muse Spark's multimodal reasoning, structured output and repair loop.

## Feasibility: what already works (as of Oct 17)

> Pre-hackathon groundwork, public at [[github.com/nickthelegend/mimic-meta]]:
> - an end-to-end offline pipeline in Python, from video to hand and object tracks to pick / move / place steps to waypoint program to inverse kinematics to a checked simulated replay, with 25 passing tests
> - on a synthetic clip with exact ground truth, both carries are found, every pick and place within **1.9 mm** and **100 ms** of the truth, and the bowl jiggling under the hand is correctly *not* counted as a carry
> - the program format and safety check: joint limits, the fingertip never below the table between waypoints, the elbow clear of the table; unsafe programs are shown but can't be sent to an arm
> - a Muse Spark writer with the repair loop (tested against a mocked API), and a SAM 3.1 client for the hosted API, one concept per request (request side done, reply parser to wire once access arrives)
> - SO-101 / Thenar arm drivers over USB serial, reused from my REACH project, with a STOP handshake before arming
> - the review web page with tracking overlay, movement score, editable program and 3-D replay
>
> **The 10 days are for the parts that need Meta's models and real footage:** swap the OpenCV stand-in for SAM 3.1, put Muse Spark in the loop on real clips, and run on the printed arm with a measured success rate.

## Plan for Oct 26 – Nov 4

| Days | What | Done when |
|---|---|---|
| 1–2 | Wire SAM 3.1 (hosted `sam-3.1`) and parse its masks into tracks | A real phone clip gives hand and object tracks |
| 3–4 | Muse Spark writes and repairs programs on real clips; heights from key frames | 10 real clips each give a program that passes the safety check |
| 5–6 | Calibration: print the mat with corner marks and auto-detect them | Mat positions within ±5 mm of a ruler |
| 7–8 | The printed arm runs it: 20 trials of 3 tasks | Success rate measured and reported honestly |
| 9–10 | Demo video, write-up, polish | Submitted before Nov 4, 9 PM ET |

## Honest limits (worth stating; judges reward candour)

> Replay is open-loop. If an object moves after filming, the arm misses it. Grasps are top-down with a parallel gripper. It needs a top-down clip over the mat. Tasks are rigid pick-and-place and slides. The next step after the hackathon is closing the loop with a camera on the arm.

## Technical skill: a past AI project you built

> **Pick one.** Each describes your own work in this repo family. Fill in links and numbers you can verify, and cut anything that isn't yours.

**Option A: REACH (an Alexa+ assistive robot arm).**
> I built REACH, an MCP server for Amazon Alexa+ that drives a printable robot arm for people with limited mobility ("Alexa, hand me my pills"). It implements the MCP spec (2025-11-25) over Streamable HTTP, with OAuth 2.1 + PKCE account linking. It drives either a simulated arm or a real SO-101 / Thenar Walker over serial and Wi-Fi WebSocket, with motion capped per joint at 25 Hz, a table guard, and a STOP handshake before arming. Places are taught by moving the arm rather than hard-coded, and the robot learns its drive routes. The end-to-end tests run a real MCP client against the server through the full OAuth flow. [[link]]

**Option B: Quiver (hearing a machine from silent video).**
> I built Quiver: film a running machine in slow motion and it measures the machine's vibration from the pixels with sub-pixel phase correlation. It plays back the machine's sound, magnifies the motion, and an LLM writes the maintenance work order. The pipeline runs OpenCV, spectral analysis, motion magnification and an LLM diagnosis behind a FastAPI app, with tests against reference signals. [[link, results]]

**Option C: ThenarLabs hardware.**
> I design printable robot hardware at ThenarLabs: the Thenar / SO-101-class arms and HOTARU, an animated desk lamp. HOTARU's CAD is modelled in SolidWorks. Its gestures are compiled from Python into firmware only after every keyframe passes a pose guard and every step a route check. It talks: speech in and out, with an LLM choosing from 60 gestures. [[link]]

**Techniques to name in any option:** computer vision (OpenCV, segmentation masks, tracking), robot kinematics (FK/IK, joint limits, safety guards), LLM structured output and tool loops, FastAPI, three.js, embedded firmware (ESP32), test-driven Python.

## Links (optional but they help verify you)

- GitHub: [[https://github.com/nickthelegend]]
- This project: [[https://github.com/nickthelegend/mimic-meta]] (the repo is private; make it public or share it before you link it)
- LinkedIn: [[ ]]
- ThenarLabs: [[site link]]. The research found no public page for the Thenar arm, so a link matters.

## Questions 13–16 (not used for selection)

Answer them honestly; they're about Meta's developer programs.

---

### Before you submit
- [ ] Fill every `[[ ]]` and remove the technical-skill options you don't use.
- [ ] Decide whether the repo goes public now or at submission (the rules aren't out yet).
- [ ] Check the form's character limits and trim the project idea if needed.
- [ ] Apply well before Oct 25, since the 20,000-spot cap can close it early.
