"""Full Phase 4 evidence runner. Real Chrome UI, local HTTP, CLI; no mocks or credentials."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback

import cv2
import httpx
import numpy as np
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "audit"
PY = ROOT / ".venv/bin/python"
LOCK = "/Volumes/Extreme SSD/Projects/grokbot/tools/heavy-slot.sh"
INITIAL = (ROOT / "AUDIT.md").read_text()
TABLE = {cells[1].strip(): cells for line in INITIAL.splitlines()
         if len(cells := line.split("|")) == 8 and cells[4].strip() in {"PENDING", "PASS", "FAIL", "UNTESTED"}}
SELECTED = [id for id, cells in TABLE.items() if cells[4].strip() != "UNTESTED"]
FIXES = {"P1": "Added favicon route.", "L4": "Removed upload preview blob src."}
for id in ["P4", "U5", "U6", "E1", "E3"]:
    FIXES[id] = "Chrome status echo not double-counted for the exact allowlisted URL/status."
RESULTS = {}
PORT = 8730
SERVER = None
HTTP = None
BASE = ""
TEMP = None
CONTEXT = None
BROWSER = None
STARTED = {}


def process_snapshot():
    output = subprocess.run(["ps", "-axo", "pid=,ppid=,comm="], capture_output=True, text=True, check=True).stdout
    return {int(pid): {"ppid": int(ppid), "command": command}
            for line in output.splitlines() if len(parts := line.strip().split(None, 2)) == 3
            for pid, ppid, command in [parts]}


def track_processes():
    snapshot = process_snapshot()
    parents = {os.getpid()}
    while children := {pid for pid, info in snapshot.items() if info["ppid"] in parents} - parents:
        parents.update(children)
    STARTED.update({pid: snapshot[pid] for pid in parents - {os.getpid()}
                    if snapshot[pid]["command"] != "/bin/ps"})


def persist(id, evidence):
    evidence["id"] = id
    evidence["url"] = BASE
    evidence["status"] = "PASS" if not evidence["failures"] else "FAIL"
    (OUT / f"{id}.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False))
    RESULTS[id] = evidence
    lines = (ROOT / "AUDIT.md").read_text().splitlines()
    for i, line in enumerate(lines):
        cells = line.split("|")
        if len(cells) == 8 and cells[1].strip() == id:
            cells[4] = f" {evidence['status']} "
            note = evidence["actual"].replace("|", "/").replace("\n", " ")
            cells[5] = f" [log](audit/{id}.json)" + (f" · [view](audit/{id}.jpg)" if evidence.get("screenshot") else "") + f" — {note} "
            fix = cells[6].strip()
            if TABLE[id][4].strip() == "FAIL" and evidence["status"] == "PASS":
                fix = FIXES.get(id, fix)
            cells[6] = f" {fix} "
            lines[i] = "|".join(cells)
    (ROOT / "AUDIT.md").write_text("\n".join(lines) + "\n")
    print(f"{id}: {evidence['status']} — {evidence['actual']}", flush=True)


class Row:
    def __init__(self, id):
        self.id = id
        self.e = {"failures": [], "observations": {}, "actual": "", "console": [], "page_errors": [], "network": []}

    def check(self, condition, message):
        if not condition:
            self.e["failures"].append(message)

    def observe(self, **values):
        self.e["observations"].update(values)

    def actual(self, text):
        self.e["actual"] = text

    def request(self, method, path, **kwargs):
        r = HTTP.request(method, path, **kwargs)
        self.e["network"].append({"method": method, "url": str(r.url), "status": r.status_code})
        return r


@contextlib.contextmanager
def row(id):
    assert id in SELECTED, f"Unselected row: {id}"
    assert id not in RESULTS, f"Duplicate row: {id}"
    r = Row(id)
    try:
        yield r
    except Exception as e:
        r.e["failures"].append(f"{type(e).__name__}: {e}")
        r.e["exception"] = traceback.format_exc()
    finally:
        if not r.e["actual"]:
            r.actual("; ".join(r.e["failures"]) or "Observed expected result.")
        persist(id, r.e)


@contextlib.contextmanager
def browser_row(id, width=1280):
    with row(id) as r:
        page = CONTEXT.new_page()
        page.set_viewport_size({"width": width, "height": 960})
        page.set_default_timeout(15000)
        allowed = []
        r.allowed = allowed
        listeners = {
            "console": lambda m: r.e["console"].append({"type": m.type, "text": m.text, "location": m.location}),
            "pageerror": lambda e: r.e["page_errors"].append(str(e)),
            "response": lambda s: r.e["network"].append({"method": s.request.method, "url": s.url, "status": s.status}),
            "requestfailed": lambda q: r.e["network"].append({"method": q.method, "url": q.url, "failed": q.failure}),
        }
        for event, callback in listeners.items():
            page.on(event, callback)
        r.page = page
        try:
            yield r
        finally:
            page.wait_for_timeout(400)
            r.observe(viewport=page.viewport_size, final_url=page.url)
            for entry in r.e["console"]:
                if entry["type"] == "error":
                    status = re.fullmatch(
                        r"Failed to load resource: the server responded with a status of (\d{3})(?: \([^()\r\n]*\))?",
                        entry["text"],
                    )
                    if status and any(url == entry["location"].get("url") and code == int(status[1])
                                      for _, url, code in r.allowed):
                        continue
                    r.e["failures"].append("Console error: " + entry["text"])
            r.e["failures"].extend("Page error: " + e for e in r.e["page_errors"])
            for n in r.e["network"]:
                if n.get("failed"):
                    r.e["failures"].append(f"Failed request: {n['url']} ({n['failed']})")
                elif n.get("status", 0) >= 400 and (n["method"], n["url"], n["status"]) not in allowed:
                    r.e["failures"].append(f"Unexpected HTTP {n['status']}: {n['url']}")
            try:
                page.screenshot(path=str(OUT / f"{id}.jpg"), type="jpeg", quality=55, timeout=15000)
                r.e["screenshot"] = f"audit/{id}.jpg"
                assert (OUT / f"{id}.jpg").stat().st_size <= 200000
            except Exception as e:
                r.e["failures"].append("Screenshot: " + str(e))
            if r.e["failures"]:
                r.actual((r.e["actual"] + " " if r.e["actual"] else "") + "Failures: " + "; ".join(r.e["failures"]))
            for event, callback in listeners.items():
                page.remove_listener(event, callback)
            page.close()


def load(r, query="?run=sample"):
    p = r.page
    p.goto(BASE + "/" + query, wait_until="load", timeout=60000)
    p.wait_for_function("!document.querySelector('#play').disabled", timeout=60000)
    p.wait_for_function("document.querySelector('#video').readyState >= 2", timeout=30000)
    p.wait_for_timeout(200)


def fetch_page(r, path, fields=None, method="POST", body=None, raw=False):
    return r.page.evaluate("""async ({path, fields, method, body, raw}) => {
      const opts = {method};
      if (fields) { const fd = new FormData(); for (const [k,v] of Object.entries(fields)) fd.append(k,v); opts.body=fd; }
      if (body !== null) { opts.body=JSON.stringify(body); opts.headers={'Content-Type':'application/json'}; }
      const response = await fetch(path, opts);
      if (raw) return {status:response.status,bytes:(await response.arrayBuffer()).byteLength};
      return {status:response.status, body:await response.json()};
    }""", {"path": path, "fields": fields, "method": method, "body": body, "raw": raw})


def options(p):
    return p.evaluate("""() => ({who:document.querySelector('#who').textContent,
      on:document.querySelector('#who').classList.contains('on'), arm:document.querySelector('#armName').textContent,
      trackers:[...document.querySelector('#tracker').options].map(o=>({value:o.value,label:o.text,disabled:o.disabled})),
      writers:[...document.querySelector('#writer').options].map(o=>({value:o.value,label:o.text,disabled:o.disabled}))})""")


def check_boot(r):
    o = options(r.page)
    r.observe(boot=o)
    r.check(o["who"] == "simulated arm · offline writer" and o["on"] and o["arm"] == "SO-101 · simulated", "Wrong boot labels or class")
    r.check(o["trackers"] == [{"value":"color","label":"OpenCV stand-in","disabled":False},{"value":"mediapipe","label":"MediaPipe hands","disabled":True},{"value":"sam3","label":"SAM 3.1 (paid)","disabled":True}], "Wrong tracker availability")
    r.check(o["writers"] == [{"value":"rules","label":"Rules (offline)","disabled":False},{"value":"muse-spark","label":"Muse Spark (paid)","disabled":True}], "Wrong writer availability")


def run_cli(r, args, name):
    proc = subprocess.run([str(PY), *args], cwd=ROOT, capture_output=True, text=True, timeout=180)
    (OUT / f"{name}.stdout.txt").write_text(proc.stdout)
    (OUT / f"{name}.stderr.txt").write_text(proc.stderr)
    r.observe(**{name: {"command": [".venv/bin/python", *args], "exit_code":proc.returncode,
                       "stdout":f"audit/{name}.stdout.txt", "stderr":f"audit/{name}.stderr.txt"}})
    return proc


def dirs():
    return {p.name for p in (ROOT / "runs").iterdir() if p.is_dir()}


def upload_http(r, path, **fields):
    with Path(path).open("rb") as f:
        return r.request("POST", "/api/analyze", files={"video":(Path(path).name,f,"video/mp4")}, data={"tracker":"color","writer":"rules","prompts":"hand, red block, green block, blue bowl",**fields})


def fixture_setup():
    short = TEMP / "short.mp4"
    nohand = TEMP / "no-hand.mp4"
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(ROOT/"samples/sample.mp4"),"-t","1","-c:v","libx264","-pix_fmt","yuv420p",str(short)],check=True)
    raw = TEMP / "no-hand-raw.mp4"
    writer = cv2.VideoWriter(str(raw),cv2.VideoWriter_fourcc(*"mp4v"),30,(960,540))
    for _ in range(90):
        writer.write(np.full((540,960,3),(198,203,207),dtype=np.uint8))
    writer.release()
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(raw),"-c:v","libx264","-pix_fmt","yuv420p",str(nohand)],check=True)
    mov = TEMP / "sample.mov"
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(ROOT/"samples/sample.mp4"),"-c:v","mpeg4","-q:v","2",str(mov)],check=True)
    (TEMP / "notes.txt").write_text("ordinary notes, not video")
    (TEMP / "garbage.mp4").write_bytes(b"not a video\x00garbage bytes")
    big = TEMP / "over-limit.mp4"
    with big.open("wb") as f:
        f.truncate(400 * 1024 * 1024 + 1)
    return short,nohand,mov,big


def execute():
    global HTTP,BASE,SERVER,PORT,TEMP,CONTEXT,BROWSER
    os.chdir(ROOT)
    with socket.socket() as sock:
        try: sock.bind(("127.0.0.1",PORT))
        except OSError:
            sock.bind(("127.0.0.1",0)); PORT=sock.getsockname()[1]
    BASE=f"http://127.0.0.1:{PORT}"
    log=(OUT/"server.log").open("w")
    SERVER=subprocess.Popen([str(ROOT/".venv/bin/uvicorn"),"server:app","--host","127.0.0.1","--port",str(PORT)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    HTTP=httpx.Client(base_url=BASE,timeout=180)
    for _ in range(120):
        try:
            if HTTP.get("/api/health").status_code==200: break
        except httpx.ConnectError: pass
        if SERVER.poll() is not None: raise RuntimeError("Server did not start")
        time.sleep(.5)
    else: raise RuntimeError("Server readiness timed out")
    with row("C1") as r:
        p=run_cli(r,["-m","mimic.pipeline","--version"],"C1")
        from mimic import __version__
        r.observe(package_version=__version__)
        r.check(p.returncode==0 and p.stdout=="mimic 0.1.0\n" and __version__=="0.1.0","Version does not match")
        r.actual("Exit 0; stdout mimic 0.1.0 plus newline; package version 0.1.0.")
    with row("C2") as r:
        p=run_cli(r,["-m","mimic.synth"],"C2")
        truth=json.loads(p.stdout)
        r.observe(truth=truth)
        r.check(p.returncode==0 and all((ROOT/"samples"/name).exists() for name in ["sample.mp4","sample.truth.json"]),"Synthetic files missing")
        r.check(all(truth[k]==v for k,v in {"fps":30,"width":960,"height":540,"prompts":["hand","red block","green block","blue bowl"]}.items()),"Wrong truth stdout")
        r.actual("Synthetic MP4 and truth written; stdout has 30 fps, 960×540 and all four prompts.")
    global TEMP
    TEMP=Path(tempfile.mkdtemp(prefix="mimic-audit-"))
    short,nohand,mov,big=fixture_setup()
    with row("C3") as r:
        p=run_cli(r,["-m","mimic.pipeline","samples/sample.mp4"],"C3-full")
        data=json.loads(p.stdout)
        q=run_cli(r,["-m","mimic.pipeline","samples/sample.mp4","--json"],"C3-program")
        program=json.loads(q.stdout)
        r.observe(check=data["check"],score=data["score"],program_keys=list(program),summary=program["summary"])
        r.check(p.returncode==q.returncode==0 and data["check"]["ok"] and data["score"]["found"]==data["score"]["expected"]==2,"Pipeline full output mismatch")
        r.check(all(k in program for k in ["summary","objects","waypoints"]) and "score" not in program and program["summary"].startswith("Put the red block in the blue bowl"),"Program-only output mismatch")
        r.actual("Both CLI modes exit 0; check.ok true; 2/2 carries; --json emits only the program.")
    with row("C4") as r:
        p=run_cli(r,["-m","mimic.pipeline",str(short)],"C4")
        r.check(p.stdout=="" and "at least 1.5 s" in p.stderr and p.returncode==2,"Short CLI rejection mismatch")
        r.actual("Exit 2; empty stdout; stderr asks for at least 1.5 s.")
    with row("H1") as r:
        s=r.request("GET","/api/health")
        expected={"ok":True,"trackers":{"color":True,"mediapipe":False,"sam3":False},"writers":{"rules":True,"muse-spark":False},"arm":"sim"}
        r.observe(response=s.json(),keys_unset=["META_API_KEY","MUSE_API_KEY","MODEL_API_KEY","MIMIC_ARM"])
        r.check(s.status_code==200 and s.json()==expected,"Health JSON differs")
        r.actual("HTTP 200; exact offline health JSON, sim arm, only color and rules available.")
    with sync_playwright() as pw:
        BROWSER=pw.chromium.launch(headless=True, executable_path=pw.chromium.executable_path)
        chrome_version = BROWSER.version
        chrome_executable = pw.chromium.executable_path
        track_processes()
        CONTEXT=BROWSER.new_context(viewport={"width":1280,"height":960},accept_downloads=True)
        CONTEXT.add_init_script("""window.auditBusyTexts=[]; new MutationObserver(()=>{const e=document.querySelector('#working');if(e && !e.hidden) {const t=document.querySelector('#workingText').textContent;if(!window.auditBusyTexts.includes(t)) window.auditBusyTexts.push(t)}}).observe(document,{subtree:true,childList:true,attributes:true,characterData:true});""")
        with browser_row("P1") as r:
            CONTEXT.clear_cookies()
            r.page.goto(BASE,wait_until="load",timeout=60000)
            r.page.wait_for_function("!document.querySelector('#play').disabled",timeout=60000)
            r.page.wait_for_function("document.querySelector('#video').readyState >= 2")
            response=r.request("GET","/")
            favicon=fetch_page(r,"/favicon.ico",method="GET",raw=True)
            labels={s:r.page.locator(s).inner_text() for s in [".mark b",".mark small","#sampleBtn","#uploadBtn"]}
            positions={s:r.page.locator(s).bounding_box() for s in ["#sampleBtn","#uploadBtn"]}
            r.observe(labels=labels,positions=positions,body_matches_file=response.content==(ROOT/"web/index.html").read_bytes(),favicon=favicon)
            r.check(favicon["status"]==200 and favicon["bytes"]>0,"Favicon is not HTTP 200 with an image body")
            r.check(response.status_code==200 and response.content==(ROOT/"web/index.html").read_bytes(),"GET / differs from web/index.html")
            r.check(list(labels.values())==["MIMIC","by ThenarLabs","Try the sample clip","Upload a clip"] and all(b["y"]+b["height"]<=960 for b in positions.values()),"Header text or first viewport mismatch")
            r.actual("HTTP 200 exact index.html body; expected mark and first-viewport header buttons; favicon HTTP 200 without console errors.")
        with browser_row("P2") as r:
            r.page.add_init_script("localStorage.removeItem('mimic.run')")
            load(r,"")
            nodes={s:r.page.locator(s).count() for s in ["#overlay","#score .blk","#steps li[data-step]","#wps li","#view canvas"]}
            busy=r.page.evaluate("window.auditBusyTexts")
            r.observe(nodes=nodes,busy_texts=busy,stored_run=r.page.evaluate("localStorage.getItem('mimic.run')"))
            r.check(any(n["method"]=="POST" and n["url"]==BASE+"/api/sample" for n in r.e["network"]),"No real POST sample")
            r.check(all(nodes.values()) and "Reading the sample clip…" in busy,"Sample components or busy message missing")
            r.actual("First clean visit POSTed sample and rendered overlay, score, six steps, program and 3-D canvas; observed busy message.")
        for id in ["H2","H3"]:
            with browser_row(id) as r:
                load(r); check_boot(r)
                r.actual("Observed offline setup state: simulated arm, disabled paid and MediaPipe options; color/rules enabled.")
        with browser_row("H4",375) as r:
            load(r); o=options(r.page)
            visible={s:r.page.locator(s).is_visible() for s in [".mark small","#who","#tracker","#writer"]}
            r.observe(visible=visible,boot=o)
            r.check(visible=={".mark small":False,"#who":False,"#tracker":True,"#writer":True},"Mobile signal visibility mismatch")
            r.check(o["trackers"][2]["disabled"] and o["writers"][1]["disabled"],"Paid options enabled")
            r.actual("At 375px the byline and who are hidden; both menus remain visible with paid options disabled.")
        with browser_row("X1b") as r:
            load(r)
            reply=fetch_page(r,"/api/sample",fields={"writer":"muse-spark"})
            out=reply["body"]
            load(r,"?run="+out["run_id"])
            label=r.page.locator("#writerName").inner_text()
            r.observe(status=reply["status"],writer=out["writer"],fallback=out["fallback"],label=label)
            r.check(reply["status"]==200 and out["writer"]=="rules" and out["fallback"].startswith("muse-spark failed") and label.endswith(" · Muse Spark was unreachable"),"Fallback behavior mismatch")
            r.actual("Missing-key write threw locally; real pipeline fell back to rules; browser displayed Muse Spark was unreachable.")
        with browser_row("P3") as r:
            load(r)
            r.page.evaluate("localStorage.setItem('mimic.run','storedmissing')")
            load(r,"?run=querymissing&sample")
            net=r.e["network"]
            r.check(any(n["method"]=="POST" and n["url"]==BASE+"/api/sample" for n in net) and not any("missing/result.json" in n["url"] for n in net),"?sample did not override stored/query run")
            r.actual("?sample overrode both missing stored id and missing ?run; POSTed sample without either run GET.")
        with browser_row("P4") as r:
            load(r)
            r.page.evaluate("localStorage.setItem('mimic.run','samplemuse')")
            load(r,"")
            stored=r.page.url
            load(r,"?run=sample")
            query=r.page.url
            r.allowed.append(("GET",BASE+"/runs/missingrun/result.json",404))
            load(r,"?run=missingrun")
            r.observe(stored_url=stored,query_url=query,missing_fallback_url=r.page.url)
            paths=[n["url"] for n in r.e["network"]]
            r.check(stored.endswith("?run=samplemuse") and query.endswith("?run=sample") and r.page.url.endswith("?run=sample") and all(BASE+p in paths for p in ["/runs/samplemuse/result.json","/runs/sample/result.json","/runs/missingrun/result.json","/api/sample"]),"Stored/query/missing flow mismatch")
            r.actual("Stored and query runs rendered; missing run returned expected 404 then POSTed sample.")
        with browser_row("P5") as r:
            load(r)
            out=r.request("GET","/runs/sample/result.json").json()
            video=r.request("GET",out["video"])
            observed={s:r.page.locator(s).inner_text() for s in ["#steps","#truth","#summary","#verdict"]}
            r.observe(check=out["check"],score=out["score"],kinds=[s["kind"] for s in out["steps"]],video=out["video"],ui=observed)
            r.check(out["check"]["ok"] and all(out["score"][k]==v for k,v in {"found":2,"expected":2,"extra":0}.items()) and out["score"]["worst_mm"]<5 and out["score"]["worst_ms"]<=200,"Wrong sample check or score")
            r.check([s["kind"] for s in out["steps"]]==["pick","move","place"]*2 and out["video"]=="/runs/sample/clip.mp4" and video.status_code==200,"Wrong steps/video")
            r.check("Put it in the blue bowl" in observed["#steps"] and "turning it 45°" in observed["#steps"] and "Against its ground truth: 2 of 2 carries found" in observed["#truth"] and observed["#summary"].startswith("Put the red block in the blue bowl") and "Safe to run." in observed["#verdict"],"Sample UI text mismatch")
            r.actual(f"Safe sample, six expected steps, video 200, 2/2 carries, {out['score']['worst_mm']} mm / {out['score']['worst_ms']} ms; expected UI copy.")
        with browser_row("P6") as r:
            load(r); p=r.page
            label=p.locator("#play").get_attribute("aria-label")
            p.locator("#play").click(); p.wait_for_timeout(1200)
            playing=p.evaluate("({time:document.querySelector('#video').currentTime,paused:document.querySelector('#video').paused,label:document.querySelector('#play').textContent,clock:document.querySelector('#robotClock').textContent})")
            p.locator("#play").click(); p.wait_for_timeout(100)
            paused=p.evaluate("({paused:document.querySelector('#video').paused,label:document.querySelector('#play').textContent})")
            r.observe(aria_label=label,playing=playing,paused=paused)
            r.check(label=="Play the clip and the replay" and playing["time"]>.5 and not playing["paused"] and playing["label"]=="Pause" and not playing["clock"].startswith("arm 0.0") and paused=={"paused":True,"label":"Play"},"Playback controls differ")
            r.actual("Play advanced video and replay together, label Pause; second click paused video and restored Play.")
        with browser_row("P7") as r:
            load(r); p=r.page
            out=r.request("GET","/runs/sample/result.json").json(); step=out["steps"][3]
            p.locator(f"#steps li[data-step='{step['id']}']").click(); p.wait_for_timeout(150)
            k=next((i for i,w in enumerate(out["replay"]["waypoints"]) if w.get("step")==step["id"]),0)
            first=next(x for x in out["replay"]["samples"] if x["w"]==k)
            got=p.evaluate("({time:document.querySelector('#video').currentTime,robot:document.querySelector('#robotClock').textContent,on:document.querySelector('#steps li.on').dataset.step})")
            expected=max(0,step.get("t_grasp",step.get("t",step.get("t0")))-.15)
            r.observe(clicked_step=step["id"],expected_video_time=expected,expected_replay_time=first["t"],observed=got)
            r.check(abs(got["time"]-expected)<.08 and abs(float(got["robot"].split()[1])-first["t"])<.08 and got["on"]==str(step["id"]),"Step seek mismatch")
            r.actual("Clicked second pick; video sought to grasp minus 0.15 s; replay clock matched first waypoint sample; step selected.")
        with browser_row("P8") as r:
            load(r); p=r.page
            p.locator("#score").scroll_into_view_if_needed()
            b=p.locator("#score").bounding_box()
            def drag(frac,y0,y1):
                x=b["x"]+b["width"]*frac
                p.mouse.move(x,b["y"]+b["height"]*y0); p.mouse.down(); p.mouse.move(x,b["y"]+b["height"]*y1,steps=8); p.mouse.up(); p.wait_for_timeout(150)
            p.locator("#play").click(); drag(.03,.75,.60)
            a=p.evaluate("({video:document.querySelector('#video').currentTime,paused:document.querySelector('#video').paused,clock:document.querySelector('#clock').textContent,robot:document.querySelector('#robotClock').textContent})")
            drag(.97,.75,.40)
            b2=p.evaluate("({video:document.querySelector('#video').currentTime,clock:document.querySelector('#clock').textContent,robot:document.querySelector('#robotClock').textContent})")
            r.observe(left_drag=a,right_drag=b2)
            r.check(a["paused"] and a["video"]>.5 and abs(b2["video"]-a["video"])<.1 and a["robot"]!=b2["robot"] and a["clock"]==b2["clock"],"Score scrubbing did not independently seek both clocks")
            r.actual("Left drag paused and scrubbed clip; right drag independently scrubbed replay; both displayed clocks updated.")
        with browser_row("P9") as r:
            load(r); p=r.page
            r.check(p.locator("#runArm").is_enabled(),"Safe Run disabled")
            with p.expect_response(BASE+"/api/execute/sample") as response:
                p.locator("#runArm").click()
            start=response.value.json(); stop_enabled=p.locator("#stopArm").is_enabled()
            p.wait_for_function("document.querySelector('#armNote').textContent === 'Finished.'",timeout=120000)
            state=fetch_page(r,"/api/arm",method="GET")
            r.observe(start=start,stop_enabled=stop_enabled,state=state,arm_note=p.locator("#armNote").inner_text())
            r.check(start=={"started":True,"backend":"sim"} and stop_enabled and state["body"]["label"]=="done" and state["body"]["error"] is None,"Simulator execute mismatch")
            r.actual("Sim execute started; Stop enabled; arm reached done with null error; UI Finished.")
        with browser_row("P10") as r:
            load(r); p=r.page
            p.locator("#runArm").click(); p.wait_for_function("!document.querySelector('#stopArm').disabled"); p.wait_for_timeout(200)
            with p.expect_response(BASE+"/api/stop") as response:
                p.locator("#stopArm").click()
            stop=response.value.json()
            p.wait_for_function("document.querySelector('#armNote').textContent === 'Stopped.'",timeout=15000)
            state=fetch_page(r,"/api/arm",method="GET")
            r.observe(stop=stop,state=state,arm_note=p.locator("#armNote").inner_text())
            r.check(stop=={"stopped":True} and state["body"]["label"]=="stopped","Stop result mismatch")
            r.actual("Stop POST returned stopped true; arm label stopped; UI Stopped.")
        with browser_row("U1") as r:
            load(r); p=r.page
            input_state=p.evaluate("({prompts:document.querySelector('#prompts').value,tracker:document.querySelector('#tracker').value,writer:document.querySelector('#writer').value})")
            with p.expect_response(BASE+"/api/analyze",timeout=90000) as response:
                p.locator("#file").set_input_files(str(ROOT/"samples/sample.mp4"))
            out=response.value.json(); p.wait_for_function("document.querySelector('#working').hidden")
            video=r.request("GET",out["video"])
            r.observe(input=input_state,status=response.value.status,run_id=out["run_id"],video=out["video"],kinds=[s["kind"] for s in out["steps"]])
            r.check(input_state=={"prompts":"hand, red block, green block, blue bowl","tracker":"color","writer":"rules"} and response.value.status==200 and [s["kind"] for s in out["steps"]]==["pick","move","place"]*2 and video.status_code==200,"Sample upload mismatch")
            r.actual("File input uploaded synthetic sample with specified prompts/color/rules; analyze 200, expected six steps, video 200.")
        with browser_row("U2") as r:
            load(r); p=r.page
            before=len([n for n in r.e["network"] if n["method"]=="POST"])
            p.locator("#file").set_input_files(str(TEMP/"notes.txt")); p.wait_for_timeout(250)
            msg=p.locator("#msg").inner_text()
            after=len([n for n in r.e["network"] if n["method"]=="POST"])
            r.observe(message=msg,posts_before=before,posts_after=after)
            r.check(msg=="notes.txt isn't a video. Choose an MP4 or MOV from your phone." and after==before,"Nonvideo validation differs")
            r.actual("Exact notes.txt rejection displayed; no POST occurred.")
        for id,clip,reason,fragment in [("U5",short,"too_short","at least 1.5 s"),("U6",nohand,"no_hand","No hand was found")]:
            with browser_row(id) as r:
                load(r); p=r.page; before=dirs()
                r.allowed.append(("POST",BASE+"/api/analyze",422))
                with p.expect_response(BASE+"/api/analyze",timeout=90000) as response:
                    p.locator("#file").set_input_files(str(clip))
                out=response.value.json(); p.wait_for_function("document.querySelector('#working').hidden")
                msg=p.locator("#msg").inner_text(); after=dirs()
                r.observe(status=response.value.status,body=out,message=msg,added_run_dirs=sorted(after-before))
                r.check(response.value.status==422 and out.get("reason")==reason and fragment in out["detail"] and msg==out["detail"] and after==before,"Clip rejection or cleanup differs")
                r.actual(f"Analyze 422/{reason}; exact detail displayed; run directory removed.")
        with browser_row("E2") as r:
            load(r); p=r.page
            program=r.request("GET","/runs/sample/result.json").json()["program"]
            with p.expect_download() as download:
                p.locator("#saveBtn").click()
            d=download.value
            text=Path(d.path()).read_text(); out=json.loads(text)
            r.observe(filename=d.suggested_filename,program_keys=list(out),waypoints=len(out["waypoints"]),contains_solved_q=any("q" in w for w in out["waypoints"]))
            (OUT/"E2-download.json").write_text(text)
            js=p.evaluate("p=>JSON.stringify(p,null,2)",program)
            r.check(d.suggested_filename=="mimic-sample.json" and text==js and all(k in out for k in ["summary","objects","waypoints"]) and not any("q" in w for w in out["waypoints"]),"Download differs")
            r.actual("Downloaded mimic-sample.json; exact pretty-printed program with summary/objects/waypoints and no solved q.")
        with browser_row("E3") as r:
            load(r); p=r.page
            p.locator("#runArm").click(); p.wait_for_function("!document.querySelector('#stopArm').disabled")
            busy=fetch_page(r,"/api/arm",method="GET")
            r.allowed.append(("POST",BASE+"/api/execute/sample",409))
            second=fetch_page(r,"/api/execute/sample")
            p.locator("#stopArm").click(); p.wait_for_function("document.querySelector('#armNote').textContent === 'Stopped.'")
            r.observe(busy=busy,second_execute=second)
            r.check(busy["body"]["busy"] and second=={"status":409,"body":{"detail":"the arm is already running a program"}},"Busy execute rejection differs")
            r.actual("Second execute while busy returned exact 409 detail; stopped simulator afterward.")
        with browser_row("E1") as r:
            load(r); p=r.page
            p.locator("#editBtn").click()
            program=json.loads(p.locator("#json").input_value())
            next(w for w in program["waypoints"] if "xyz" in w)["xyz"]=[0.0,0.9,0.07]
            p.locator("#json").fill(json.dumps(program))
            with p.expect_response(BASE+"/api/recheck/sample") as response:
                p.locator("#recheck").click()
            out=response.value.json(); p.wait_for_function("document.querySelector('#editor').hidden")
            r.allowed.append(("POST",BASE+"/api/execute/sample",422))
            execution=fetch_page(r,"/api/execute/sample")
            note=p.locator("#armNote").inner_text(); disabled=p.locator("#runArm").is_disabled()
            r.observe(check=out["check"],execute=execution,note=note,run_disabled=disabled)
            r.check(out["check"]["ok"] is False and any(x["issue"]=="xyz [0.0, 0.9, 0.07] is not on this table (metres?)" for x in out["check"]["issues"]) and disabled and note=="Running is locked until the check passes." and execution=={"status":422,"body":{"detail":"the program has unresolved issues; fix them before running it on an arm"}},"Unsafe program lock differs")
            r.actual("Edited unsafe xyz; recheck failed with exact reach issue; Run locked; execute returned exact 422 detail.")
        # Regenerate the actual sample after the destructive editor check.
        HTTP.post("/api/sample")
        with browser_row("L1") as r:
            load(r); p=r.page
            boxes={s:p.locator(s).bounding_box() for s in [".clipR",".scoreR",".replayR"]}
            size=p.evaluate("({width:innerWidth,scroll:document.documentElement.scrollWidth})")
            r.observe(boxes=boxes,size=size)
            r.check(max(b["y"] for b in boxes.values())-min(b["y"] for b in boxes.values())<2 and boxes[".clipR"]["x"]<boxes[".scoreR"]["x"]<boxes[".replayR"]["x"] and size["scroll"]<=size["width"],"Desktop placement or overflow differs")
            r.actual("At 1280px clip, score, replay share first grid row; no horizontal overflow.")
        with browser_row("L2",375) as r:
            load(r); p=r.page
            selectors=[".clipR",".replayR",".scoreR",".stepsR",".progR"]
            boxes={s:p.locator(s).bounding_box() for s in selectors}
            orders=p.evaluate("ss=>ss.map(s=>getComputedStyle(document.querySelector(s)).order)",selectors)
            size=p.evaluate("({width:innerWidth,scroll:document.documentElement.scrollWidth})")
            buttons={}
            for s in ["#uploadBtn","#sampleBtn","#play","#runArm"]:
                p.locator(s).scroll_into_view_if_needed()
                buttons[s]={"visible":p.locator(s).is_visible(),"enabled":p.locator(s).is_enabled(),"label":p.locator(s).inner_text(),"box":p.locator(s).bounding_box()}
            r.observe(boxes=boxes,orders=orders,size=size,buttons=buttons)
            r.check(orders==["0","1","2","3","4"] and [boxes[s]["y"] for s in selectors]==sorted(boxes[s]["y"] for s in selectors) and max(b["x"] for b in boxes.values())-min(b["x"] for b in boxes.values())<2 and size["scroll"]<=375,"Mobile layout or overflow differs")
            r.check(all(v["visible"] and v["enabled"] and v["box"]["x"]>=0 and v["box"]["x"]+v["box"]["width"]<=375 for v in buttons.values()) and buttons["#uploadBtn"]["label"]=="Upload" and buttons["#sampleBtn"]["label"]=="Try the clip","Mobile controls unreachable or incorrect")
            p.evaluate("scrollTo(0,0)")
            r.actual("375px single column in clip/replay/score/steps/program order, no overflow; shortened Upload/Try the clip and Play/Run controls reachable.")
        with browser_row("L3") as r:
            load(r,"?sample")
            urls=[n["url"] for n in r.e["network"] if n.get("status")==200]
            r.check("https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js" in urls and any("https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/" in u for u in urls),"three.js import map modules not loaded")
            r.actual("Real sample load and three.js/addons CDN requests captured; no console error, page error, failed request or unexpected HTTP error.")
        with browser_row("L4") as r:
            load(r); p=r.page
            ffmpeg=subprocess.run(["ffmpeg","-version"],capture_output=True,text=True).stdout.splitlines()[0]
            ffprobe=subprocess.run(["ffprobe","-version"],capture_output=True,text=True).stdout.splitlines()[0]
            records=[]
            for clip in [mov,ROOT/"samples/sample.mp4"]:
                with p.expect_response(BASE+"/api/analyze",timeout=90000) as response:
                    p.locator("#file").set_input_files(str(clip))
                out=response.value.json(); p.wait_for_function("document.querySelector('#working').hidden")
                stored=ROOT/out["video"].lstrip("/")
                probe=json.loads(subprocess.run(["ffprobe","-v","error","-show_entries","stream=codec_name,pix_fmt","-of","json",str(stored)],capture_output=True,text=True,check=True).stdout)
                records.append({"status":response.value.status,"source":clip.name,"video":out["video"],"probe":probe,"unchanged":hashlib.sha256(clip.read_bytes()).digest()==hashlib.sha256(stored.read_bytes()).digest()})
            r.observe(ffmpeg_path=shutil.which("ffmpeg"),ffprobe_path=shutil.which("ffprobe"),ffmpeg_version=ffmpeg,ffprobe_version=ffprobe,uploads=records)
            r.check(shutil.which("ffmpeg")=="/opt/homebrew/bin/ffmpeg" and "version 8.1.1" in ffmpeg and shutil.which("ffprobe") is not None,"ffmpeg machine branch differs")
            r.check(records[0]["status"]==records[1]["status"]==200 and records[0]["video"].endswith("/clip.mp4") and records[0]["probe"]["streams"][0]=={"codec_name":"h264","pix_fmt":"yuv420p"} and records[1]["video"].endswith("/input.mp4") and records[1]["unchanged"],"Reencode/passthrough differs")
            r.actual("ffmpeg 8.1.1 and ffprobe present; browser-uploaded MPEG4 MOV became H264/yuv420p clip.mp4; H264 MP4 remained byte-identical input.mp4.")
        track_processes()
        CONTEXT.close(); CONTEXT=None
        BROWSER.close(); BROWSER=None
    with row("U3") as r:
        before=dirs(); response=upload_http(r,TEMP/"garbage.mp4"); after=dirs()
        r.observe(response=response.json(),added_dirs=sorted(after-before))
        r.check(response.status_code==422 and after==before,"Garbage status or cleanup differs")
        r.actual("Garbage MP4 bytes returned 422; no run directory retained.")
    for id,fields,detail in [("U4",{"tracker":"magic"},"unknown tracker 'magic'"),("U7",{"corners":"not-json"},"corners must be JSON: four [x, y] points"),("U11",{"writer":"magic"},"unknown writer 'magic'")]:
        with row(id) as r:
            response=upload_http(r,ROOT/"samples/sample.mp4",**fields)
            r.observe(response=response.json())
            r.check(response.status_code==400 and response.json()=={"detail":detail},"Form validation differs")
            r.actual(f"HTTP 400; exact detail: {detail}.")
    with row("U8") as r:
        before=dirs(); response=upload_http(r,big); after=dirs()
        r.observe(file_bytes=big.stat().st_size,response=response.json(),added_dirs=sorted(after-before))
        r.check(response.status_code==413 and response.json()=={"detail":"clip is over 400 MB; trim it to the task"} and before==after,"Oversize status or cleanup differs")
        r.actual("Uploaded 419430401 bytes; HTTP 413 exact trim detail; run directory removed.")
    with row("U9") as r:
        responses=[]
        for target in ["/runs/../server.py","/runs/sample/secret.txt"]:
            # httpx normalizes literal dot segments; raw_path sends the requested traversal exactly.
            url=httpx.URL(BASE).copy_with(raw_path=target.encode())
            response=r.request("GET",url)
            responses.append({"raw_path":target,"status":response.status_code})
        r.observe(responses=responses)
        r.check(all(s["status"]==404 for s in responses),"Run path accepted")
        r.actual("Both literal /runs/../server.py and /runs/sample/secret.txt returned 404.")
    with row("U10") as r:
        response=r.request("POST","/api/execute/nope")
        r.observe(response=response.json())
        r.check(response.status_code==404 and response.json()=={"detail":"no such run"},"Unknown execute mismatch")
        r.actual("Unknown execute id returned HTTP 404, detail no such run.")
    with row("N1") as r:
        response=r.request("POST","/api/recheck/sample",json={})
        r.observe(response=response.json())
        r.check(response.status_code==400 and response.json()=={"detail":'send {"program": {...}}'},"Missing program validation differs")
        r.actual('HTTP 400; exact detail send {"program": {...}}.')
    if set(SELECTED)!=set(RESULTS):
        raise RuntimeError("Rows not executed: "+str(set(SELECTED)-set(RESULTS)))
    return {"base_url":BASE,"chrome_version":chrome_version,"chrome_executable":chrome_executable,"rows_executed":len(RESULTS)}


if __name__ == "__main__":
    metadata={"scope":"Phase 4 full rerun; all non-UNTESTED table rows; real local server, offline tracker/writer and SimArm; no keys, Meta calls, serial, mocks or product changes.","lock_acquired_before_runner":True,"heavy_slot":"mimic-audit-reverify","selected_rows":SELECTED,"processes_not_killed":[]}
    try:
        # Never inspect credential values. The shell removes these variable names before launch.
        assert all(k not in os.environ for k in ["META_API_KEY","MUSE_API_KEY","MODEL_API_KEY","MIMIC_ARM","MIMIC_WRITER"])
        metadata.update(execute())
    except BaseException:
        metadata["runner_error"]=traceback.format_exc()
        raise
    finally:
        track_processes()
        if CONTEXT:
            try: CONTEXT.close()
            except Exception: pass
        if BROWSER:
            try: BROWSER.close()
            except Exception: pass
        if SERVER:
            metadata["server_pid"]=SERVER.pid
            SERVER.terminate()
            try: SERVER.wait(timeout=15)
            except subprocess.TimeoutExpired:
                SERVER.kill(); SERVER.wait(timeout=10)
            metadata["server_exit_code"]=SERVER.returncode
        if HTTP: HTTP.close()
        if TEMP: shutil.rmtree(TEMP,ignore_errors=True)
        snapshot=process_snapshot()
        remaining={pid: info for pid,info in STARTED.items() if pid in snapshot and snapshot[pid]==info}
        for pid in remaining:
            try: os.kill(pid, 15)
            except ProcessLookupError: pass
        if remaining: time.sleep(1)
        snapshot=process_snapshot()
        for pid,info in remaining.items():
            if snapshot.get(pid)==info:
                try: os.kill(pid, 9)
                except ProcessLookupError: pass
        snapshot=process_snapshot()
        metadata["processes_not_killed"]=[pid for pid,info in STARTED.items() if snapshot.get(pid)==info]
        (OUT/"processes.json").write_text(json.dumps({"runner_pid":os.getpid(),"started":[{"pid":pid,**info} for pid,info in STARTED.items()],"remaining":metadata["processes_not_killed"]},indent=2))
        released=subprocess.run([LOCK,"release","mimic-audit-reverify"],capture_output=True,text=True)
        metadata["heavy_slot_released"]=released.returncode==0
        metadata["counts"]={s:sum(e["status"]==s for e in RESULTS.values()) for s in ["PASS","FAIL"]}
        metadata["counts"]["UNTESTED"]=sum("| UNTESTED |" in line for line in INITIAL.splitlines())
        (OUT/"run.json").write_text(json.dumps(metadata,indent=2))
