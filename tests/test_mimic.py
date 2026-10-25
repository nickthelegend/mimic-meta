"""MIMIC end to end, offline: a synthetic clip with ground truth through the tracker, the
segmenter, both program writers (Muse Spark against a mocked API), the safety check, the
simulated arm and the web server. Nothing here touches the network or a paid API."""

import asyncio
import json
import math
import socket

import cv2
import httpx
import numpy as np
import pytest

from mimic import __version__
from mimic import arm as A
from mimic import kinematics as K
from mimic import program as P
from mimic import sim, tracks
from mimic.calibrate import Calibration
from mimic.pipeline import ClipRejected, main, recheck, run
from mimic.segment import segment
from mimic.synth import make_sample
from mimic.writer import MuseSparkWriter, RuleWriter


@pytest.fixture(scope="session")
def sample(tmp_path_factory):
    p = tmp_path_factory.mktemp("clip") / "sample.mp4"
    truth = make_sample(p)
    return p, truth


@pytest.fixture(scope="session")
def result(sample):
    p, truth = sample
    return run(p, truth["prompts"], truth=truth)


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ------------------------------------------------------------------ kinematics ---

def test_fk_matches_reach_geometry():
    # REACH's "pills" pose: solved there for an item ~23 cm out at table height, gripper down
    tip = K.fk([-48.6, 54.6, 47.1, 78.3, 0, 8])
    assert math.hypot(tip[0], tip[1]) == pytest.approx(0.2268, abs=1e-3)
    assert tip[2] == pytest.approx(0.0398, abs=1e-3)


def test_ik_round_trips_over_the_mat():
    rng = np.random.default_rng(0)
    cal = Calibration.default(960, 540)
    for _ in range(200):
        x, y = cal.point([rng.uniform(0, 960), rng.uniform(0, 540)])
        z = rng.uniform(0.01, 0.08)
        if not K.reachable((x, y, z)):
            continue
        q = K.ik((x, y, z), yaw=rng.uniform(-180, 180))
        assert np.allclose(K.fk(q), (x, y, z), atol=1e-4)
        assert np.all(q[:5] >= K.LO[:5] - 1e-6) and np.all(q[:5] <= K.HI[:5] + 1e-6)


def test_most_of_the_mat_is_reachable_at_grasp_and_travel_height():
    cal = Calibration.default(960, 540)
    pts = [cal.point([u, v]) for u in range(40, 960, 80) for v in range(40, 540, 80)]
    for z in (0.015, 0.07):
        ok = sum(K.reachable((x, y, z)) for x, y in pts) / len(pts)
        assert ok > 0.85, (z, ok)


def test_ik_refuses_what_the_arm_cannot_reach():
    with pytest.raises(K.Unreachable):
        K.ik((0.0, 0.6, 0.02))
    with pytest.raises(K.Unreachable):
        K.ik((0.0, -0.2, 0.02))  # behind the base


def test_jaw_yaw_sets_wrist_roll():
    straight = K.ik((0.0, 0.25, 0.02), yaw=0)  # jaws close along x, arm pointing along y
    assert straight[4] == pytest.approx(0, abs=1e-6)
    turned = K.ik((0.0, 0.25, 0.02), yaw=30)
    assert turned[4] == pytest.approx(30, abs=1e-6)
    assert K.ik((0.0, 0.25, 0.02), yaw=210)[4] == pytest.approx(30, abs=1e-6)  # parallel jaws: 180 deg symmetric


# ------------------------------------------------------------------ tracking and segmentation ---

def test_tracker_follows_every_prompt(sample):
    p, truth = sample
    t = tracks.ColorTracker().track(p, truth["prompts"])
    assert t.n_frames == 300 and t.fps == 30
    seen = {k.label: len(k.frames) / t.n_frames for k in t.tracks}
    assert seen["red block"] > 0.95 and seen["green block"] > 0.95 and seen["blue bowl"] > 0.95
    assert seen["hand"] > 0.7  # it enters and leaves the frame


def test_auto_prompts_find_the_coloured_objects(sample):
    t = tracks.ColorTracker().track(sample[0], None)
    assert [k.label for k in t.tracks] == ["hand", "red object", "green object", "blue object"]


def test_steps_match_ground_truth(result, sample):
    s = result["score"]
    assert s["found"] == 2 and s["expected"] == 2 and s["extra"] == 0  # the bowl wobbling under the hand is not a carry
    assert s["worst_mm"] < 5, s
    assert s["worst_ms"] <= 200, s
    assert all(c["onto_ok"] for c in s["carries"])
    kinds = [x["kind"] for x in result["steps"]]
    assert kinds == ["pick", "move", "place"] * 2
    truth = sample[1]["carries"]
    cal = Calibration.default(960, 540)
    for step, c, key in ((result["steps"][0], truth[0], "yaw_from"), (result["steps"][5], truth[1], "yaw_to")):
        want = cal.angle(c["from_px"], c[key])
        sym = step["sym"]
        assert abs(((step["yaw"] - want) + sym / 2) % sym - sym / 2) < 4


def test_turns_and_texts(result):
    texts = [s["text"] for s in result["steps"]]
    assert texts[2] == "Put it in the blue bowl"
    assert "turning it 45°" in texts[4]


def test_no_hand_no_carry():
    # an object sliding with nobody touching it (a hand is tracked, but far away) is not a demonstration
    n, w, h = 60, 320, 180
    frames = []
    for i in range(n):
        f = np.full((h, w, 3), 200, np.uint8)
        x = 60 + int(150 * min(1, max(0, (i - 15) / 30)))
        cv2.rectangle(f, (x, 80), (x + 24, 104), (40, 40, 210), -1)
        cv2.circle(f, (300, 20), 14, (150, 182, 228), -1)
        frames.append(f)
    ct = tracks.ColorTracker()
    trs = [tracks.Track(0, "hand", "hand"), tracks.Track(1, "red block", "object")]
    state = {}
    for i, f in enumerate(frames):
        ct.process(f, i, trs, 1.0, state)
    t = tracks.Tracks(fps=30, width=w, height=h, n_frames=n, backend="color", tracks=trs)
    assert segment(t)["steps"] == []
    t.tracks = [trs[1]]  # and with no hand tracked at all, the motion alone is taken as the carry
    assert [s["kind"] for s in segment(t)["steps"]] == ["pick", "move", "place"]


def write_clip(p, frames, fps=30):
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        vw.write(f)
    vw.release()
    return p


@pytest.fixture
def short_clip(sample, tmp_path):
    # the first second of the sample: a real scene, just too short to show a pick and place
    r = tracks.FrameReader(sample[0])
    return write_clip(tmp_path / "short.mp4", [f for _, f in zip(range(int(r.fps)), r)], int(r.fps))


@pytest.fixture
def handless_clip(tmp_path):
    # two seconds of a block sliding across the mat with nobody in shot
    frames = []
    for i in range(60):
        f = np.full((180, 320, 3), 200, np.uint8)
        x = 60 + 3 * i
        cv2.rectangle(f, (x, 80), (x + 24, 104), (40, 40, 210), -1)
        frames.append(f)
    return write_clip(tmp_path / "handless.mp4", frames)


def test_rejects_clips_shorter_than_the_minimum(short_clip):
    with pytest.raises(ClipRejected) as e:
        run(short_clip, ["hand", "red block"])
    assert e.value.reason == "too_short"
    assert "1.0 s long" in str(e.value) and "at least 1.5 s" in str(e.value)


def test_rejects_clips_with_no_hand(handless_clip):
    with pytest.raises(ClipRejected) as e:
        run(handless_clip, ["hand", "red block"])
    assert e.value.reason == "no_hand"
    assert "No hand was found" in str(e.value)


def test_cli_reports_a_rejected_clip(short_clip, capsys):
    assert main([str(short_clip), "hand, red block"]) == 2
    out = capsys.readouterr()
    assert out.out == "" and "at least 1.5 s" in out.err


def test_cli_prints_the_package_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert capsys.readouterr().out == f"mimic {__version__}\n"


def test_frame_reader_thins_slow_motion(tmp_path):
    p = tmp_path / "slowmo.mp4"
    vw = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), 120, (1920, 1080))
    for i in range(48):
        vw.write(np.full((1080, 1920, 3), i * 5, np.uint8))
    vw.release()
    r = tracks.FrameReader(p)
    frames = list(r)
    assert r.fps == 30 and len(frames) == 12
    assert frames[0].shape[1] == tracks.MAX_W and (r.width, r.height) == (1920, 1080)


# ------------------------------------------------------------------ program, check, replay ---

def test_program_is_safe_and_puts_things_where_the_hand_did(result):
    assert result["check"]["ok"], result["check"]["issues"]
    end = result["replay"]["objects_end"]
    places = [s for s in result["steps"] if s["kind"] == "place"]
    for pl in places:
        assert math.dist(end[pl["object"]], pl["m"]) < 0.003
    bowl = next(o for o in result["scene"] if o["label"] == "blue bowl")
    assert end["blue bowl"] == bowl["m"]  # never touched
    tip, elbow = sim.lowest(result["replay"]["samples"])
    assert tip >= P.TABLE_CLEARANCE - 1e-3 and elbow >= P.ELBOW_CLEARANCE
    assert result["replay"]["waypoints"][-1]["pose"] == "home"


def test_program_json_is_plain_and_editable(result):
    prog = result["program"]
    json.dumps(prog)
    assert prog["writer"] == "rules" and prog["summary"].startswith("Put the red block in the blue bowl")
    assert all("q" not in w for w in prog["waypoints"])
    assert {w["grip"] for w in prog["waypoints"]} == {"open", "close", "hold"}


def test_cli_json_prints_only_the_program(result, sample, capsys):
    p, truth = sample
    assert main([str(p), ", ".join(truth["prompts"]), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == result["program"]


def test_check_rejects_unsafe_programs():
    bad = {"summary": "x", "waypoints": [
        {"label": "into the table", "xyz": [0.0, 0.25, -0.01], "grip": "open"},
        {"label": "too far", "xyz": [0.0, 0.36, 0.05], "grip": "open"},
        {"label": "nonsense grip", "xyz": [0.0, 0.25, 0.05], "grip": "squeeze"},
        {"label": "millimetres by mistake", "xyz": [10, 250, 50], "grip": "open"},
        {"label": "no position", "grip": "open"},
    ]}
    c = P.compile(bad)
    assert not c["ok"]
    msgs = " | ".join(i["issue"] for i in c["issues"])
    for want in ("press into the table", "out of the arm's reach", "grip must be", "not on this table", "three numbers"):
        assert want in msgs, msgs


def test_recheck_after_editing(result):
    prog = json.loads(json.dumps(result["program"]))
    prog["waypoints"][0]["xyz"][2] = 0.09  # approach higher
    out = recheck(prog, result)
    assert out["check"]["ok"]
    assert out["replay"]["waypoints"][0]["xyz"][2] == 0.09
    prog["waypoints"][1]["xyz"] = [0.0, 0.5, 0.02]
    out = recheck(prog, result)
    assert not out["check"]["ok"] and out["check"]["issues"][0]["waypoint"] == 1
    # the unreachable waypoint stays in the program you edit, at the index its issue names
    assert out["program"]["waypoints"][1]["xyz"] == [0.0, 0.5, 0.02]
    assert len(out["program"]["waypoints"]) == len(prog["waypoints"])
    assert [w["src"] for w in out["replay"]["waypoints"][:3]] == [0, 2, 3]


def test_simulation_moves_exactly_like_the_arm(monkeypatch):
    wps = [{"q": [20, 30, 40, 50, 10, 60], "speed": 1.0}, {"q": [-10, 50, 30, 70, -20, 8], "speed": 0.5}]
    samples = sim.simulate(wps)
    a = A.SimArm()

    async def no_wait(_):
        return None

    monkeypatch.setattr(A.asyncio, "sleep", no_wait)  # real-time steps, without the real time
    trail = []
    orig = a._write

    async def spy(q):
        trail.append(np.round(q, 2).tolist())
        await orig(q)

    a._write = spy

    async def go():
        for w in wps:
            await a.move(w["q"], w["speed"])

    asyncio.run(go())
    assert samples[-1]["q"] == np.round(a.q, 2).tolist()
    # the same 25 Hz steps (the arm writes each final pose once more before it returns)
    assert len(trail) - len(wps) == len(samples) - 1
    assert [s["q"] for s in samples[1:]] == [q for k, q in enumerate(trail) if k == 0 or q != trail[k - 1]]


def test_replay_drives_an_arm_and_refuses_unchecked_programs(result):
    a = A.SimArm()
    a.speedup = 200
    seen = []
    prog = {"ok": True, "waypoints": result["replay"]["waypoints"]}
    asyncio.run(A.replay(prog, a, on_step=lambda i, w: seen.append(w["label"])))
    assert np.allclose(a.q, K.HOME) and seen[0] == "above the red block" and seen[-1] == "home"
    with pytest.raises(ValueError):
        asyncio.run(A.replay({"ok": False, "waypoints": prog["waypoints"]}, a))


def test_stop_interrupts_a_replay(result):
    a = A.SimArm()
    a.speedup = 5

    async def go():
        task = asyncio.create_task(A.replay({"ok": True, "waypoints": result["replay"]["waypoints"]}, a))
        await asyncio.sleep(0.2)
        await a.stop()
        with pytest.raises(A.Stopped):
            await task

    asyncio.run(go())


# ------------------------------------------------------------------ Muse Spark (mocked) ---

def test_muse_spark_writes_then_repairs_against_the_check(result):
    steps = result["steps"]
    good = RuleWriter().write(steps)
    bad = json.loads(json.dumps(good))
    bad["waypoints"][1]["xyz"][2] = -0.02  # first try pushes into the table
    replies = [bad, good]
    calls = []

    def handler(req: httpx.Request):
        body = json.loads(req.content)
        calls.append(body)
        assert req.url.path == "/v1/chat/completions"
        assert req.headers["authorization"] == "Bearer test-key"
        assert body["model"] == "muse-spark-1.3" and body["response_format"]["type"] == "json_schema"
        prog = replies[len(calls) - 1]
        return httpx.Response(200, json={"choices": [{"message": {"content": "```json\n" + json.dumps(prog) + "\n```"}}]})

    w = MuseSparkWriter(base="https://api.meta.ai/v1", key="test-key", transport=httpx.MockTransport(handler))
    out = w.write(steps, frames=[b"\xff\xd8jpeg"])
    assert len(calls) == 2
    first = calls[0]["messages"][1]["content"]
    assert first[0]["type"] == "text" and first[1]["type"] == "image_url"
    assert "press into the table" in calls[1]["messages"][-1]["content"]  # the check's issues went back to it
    assert [len(r["issues"]) for r in out["trace"]] == [1, 0]
    assert P.compile(out)["ok"] and out["writer"] == "muse-spark"


def test_muse_spark_failure_falls_back_to_rules(sample, monkeypatch):
    monkeypatch.setenv("META_API_KEY", "test-key")
    monkeypatch.setenv("MUSE_API_BASE", f"http://127.0.0.1:{free_port()}/v1")  # nothing listens here
    p, truth = sample
    r = run(p, truth["prompts"], writer="muse-spark")
    assert r["writer"] == "rules" and r["fallback"].startswith("muse-spark failed")
    assert r["check"]["ok"]


def test_paid_writer_is_never_the_default(sample, monkeypatch):
    monkeypatch.setenv("META_API_KEY", "test-key")
    monkeypatch.delenv("MIMIC_WRITER", raising=False)
    from mimic.writer import get_writer

    assert get_writer(None).name == "rules"


# ------------------------------------------------------------------ SAM 3.1 client (mocked) ---

def test_sam3_client_uploads_once_and_asks_one_concept_per_request(sample, tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(sample[0].read_bytes())
    seen = []

    def handler(req: httpx.Request):
        seen.append(req.url.path)
        if req.url.path == "/v1/files":
            return httpx.Response(200, json={"id": "file-1"})
        body = json.loads(req.content)
        assert body["model"] == "sam-3.1"
        text = [c for c in body["input"][0]["content"] if c["type"] == "input_text"][0]["text"]
        assert "," not in text  # one concept per request: lists match nothing
        return httpx.Response(200, json={"output_text": "<raw special tokens>"})

    t = tracks.Sam3Tracker(key="k", transport=httpx.MockTransport(handler))
    with pytest.raises(NotImplementedError):
        t.track(clip, ["hand"])
    assert seen == ["/v1/files", "/v1/responses"]
    assert json.loads((tmp_path / "clip.sam-hand.json").read_text())["output_text"] == "<raw special tokens>"


def test_decoded_masks_become_the_same_tracks():
    sq = lambda x, y, s: [[x, y], [x + s, y], [x + s, y + s], [x, y + s]]  # noqa: E731
    d = {"fps": 30, "width": 640, "height": 360, "n_frames": 3, "objects": [
        {"prompt": "hand", "obj_id": 0, "frames": [{"i": i, "poly": sq(10 + i, 10, 40)} for i in range(3)]},
        {"prompt": "cup", "obj_id": 1, "frames": [{"i": i, "poly": sq(200, 100, 30)} for i in range(3)]},
        {"prompt": "cup", "obj_id": 2, "frames": [{"i": 1, "poly": sq(300, 100, 30)}]},
    ]}
    t = tracks.from_masks(d, ["hand", "cup"])
    assert [(k.label, k.kind) for k in t.tracks] == [("hand", "hand"), ("cup 1", "object"), ("cup 2", "object")]
    assert t.tracks[1].frames[0]["c"] == [215.0, 115.0]


# ------------------------------------------------------------------ web server ---

@pytest.fixture
def client(tmp_path, monkeypatch, sample):
    monkeypatch.setenv("MIMIC_RUNS", str(tmp_path / "runs"))
    import importlib

    import server

    importlib.reload(server)
    server.SAMPLE = sample[0]
    server.ARM.speedup = 400
    from fastapi.testclient import TestClient

    with TestClient(server.app) as c:
        yield c


def test_server_sample_upload_recheck_and_run(client, sample):
    assert client.get("/api/health").json()["writers"] == {"rules": True, "muse-spark": False}
    r = client.post("/api/sample").json()
    assert r["check"]["ok"] and r["score"]["found"] == 2 and r["video"] == "/runs/sample/clip.mp4"
    assert client.get(r["video"]).status_code == 200
    assert client.get("/").status_code == 200

    with open(sample[0], "rb") as f:
        up = client.post("/api/analyze", files={"video": ("demo.mp4", f, "video/mp4")},
                         data={"prompts": "hand, red block, green block, blue bowl"})
    assert up.status_code == 200, up.text
    u = up.json()
    assert [s["kind"] for s in u["steps"]] == ["pick", "move", "place"] * 2
    assert client.get(u["video"]).status_code == 200

    prog = u["program"]
    prog["waypoints"][0]["xyz"] = [0.0, 0.9, 0.07]
    bad = client.post(f"/api/recheck/{u['run_id']}", json={"program": prog}).json()
    assert not bad["check"]["ok"]
    assert client.post(f"/api/execute/{u['run_id']}").status_code == 422  # refused: it failed the check

    assert client.post("/api/execute/sample").json()["started"]
    for _ in range(200):
        s = client.get("/api/arm").json()
        if not s["busy"]:
            break
        asyncio.run(asyncio.sleep(0.02))
    assert s["label"] == "done" and s["error"] is None


def test_server_rejects_bad_input(client):
    assert client.post("/api/analyze", files={"video": ("x.mp4", b"not a video", "video/mp4")}).status_code == 422
    assert client.post("/api/analyze", files={"video": ("x.mp4", b"x", "video/mp4")}, data={"tracker": "magic"}).status_code == 400
    assert client.get("/runs/../server.py").status_code == 404
    assert client.get("/runs/sample/secret.txt").status_code == 404
    assert client.post("/api/execute/nope").status_code == 404


@pytest.mark.parametrize("clip, reason, says", [("short_clip", "too_short", "at least 1.5 s"),
                                                ("handless_clip", "no_hand", "No hand was found")])
def test_server_explains_a_rejected_clip(client, request, clip, reason, says):
    with open(request.getfixturevalue(clip), "rb") as f:
        r = client.post("/api/analyze", files={"video": ("demo.mp4", f, "video/mp4")}, data={"prompts": "hand, red block"})
    assert r.status_code == 422
    assert r.json()["reason"] == reason and says in r.json()["detail"]  # the page shows detail as it is
    import server

    assert not any(server.RUNS.iterdir())  # the rejected upload isn't kept
