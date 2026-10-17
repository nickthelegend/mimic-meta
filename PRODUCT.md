# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Plain HTML/CSS/JS in one file (`web/index.html`), three.js from a CDN import map for the 3-D replay, served by the FastAPI app in `server.py`. Set by the task brief, matching the sibling REACH and Quiver pages.

## Users

**Primary: ThenarLabs demonstrators** (confirmed). People paid to film themselves doing tabletop tasks for the Thenar corpus. They film on a phone, upload the clip, and need to see quickly whether MIMIC understood it: were the hand and objects tracked, are the pick / move / place steps right, is the robot program safe, does the replayed arm do the same thing. Throughput and review come first: many clips, each judged in under a minute.

Secondary (inferred from the hackathon brief, not confirmed as an audience for this page): Meta hackathon judges watching the demo video.

## Product Purpose

MIMIC turns one phone video of a person doing a task into a program a printable robot arm can run. SAM 3.1 (OpenCV stand-in until access arrives) tracks hands and objects, a segmenter finds the pick / move / place steps, Muse Spark (or offline rules) writes task-space waypoints, and deterministic code solves the arm's joints, replays the program in simulation and refuses anything unsafe. Success: a demonstrator can tell from one screen whether a clip is good enough to keep, and the same program runs on a real SO-101 / Thenar arm.

## Positioning

Research systems (MimicPlay, R+X, OKAMI, Vid2Robot, Phantom) learn policies from human video and need robot data, depth cameras or lab rigs. MIMIC produces a readable, editable symbolic program from a single monocular phone clip, checked before it can move a $200-300 printable arm. No teleop rig, no training run. That makes every phone owner a possible demonstrator, which is the ThenarLabs corpus story.

## Operating Context

- Filming: top-down phone video over the arm's mat (24 x 13.5 cm, starting 17.5 cm in front of the base), filmed from the side the robot will stand on.
- Review: on a laptop at a desk, sometimes on the phone that filmed the clip.
- The arm: SO-101 / Thenar follower over USB serial, or the simulator.
- A synthetic sample clip with exact ground truth (`samples/sample.mp4` via `mimic/synth.py`) for demos and tests.

## Capabilities and Constraints

- Trackers: `color` (offline OpenCV), `mediapipe` (optional hand landmarks), `sam3` (Meta Model API; paid; reply parsing not wired yet).
- Writers: `rules` (offline, default) and `muse-spark` (paid Meta Model API; only when picked).
- Program waypoints are fingertip positions in metres plus jaw yaw and grip; joint angles are never written by the model.
- Programs with issues are shown but never sent to an arm.
- Clips are capped at 120 s, thinned to 30 fps, analysed at 640 px width.
- Undecided: accept/reject workflow and corpus upload for demonstrators (not built).

## Brand Commitments

Name: **MIMIC**, credited "by ThenarLabs" (confirmed). The Thenar / SO-101 arm is named as the hardware. No other ThenarLabs styling is binding.

## Evidence on Hand

- Ground-truth score on the synthetic clip: both carries found, pick/place within 2 mm and 100 ms (`tests/test_mimic.py`).
- No real demonstrator footage, users, testimonials or hardware runs yet. Do not fabricate any.

## Product Principles

1. Show what the machine understood, next to what the person did, so a reviewer can judge it at a glance.
2. Every claim is checkable: positions in millimetres, times in seconds, issues in plain words.
3. Nothing reaches the arm unchecked; unsafe states are explicit, never hidden.
4. Paid models are opt-in, never the silent default.

## Accessibility & Inclusion

Not established beyond the standard: WCAG AA contrast, keyboard operation, reduced motion respected.
