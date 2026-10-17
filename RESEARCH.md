# MIMIC: research notes

Compiled Oct 17, 2026, from read-only web research. Every claim links to its source. **Unverified** means no primary source confirmed it. Re-check exact wording on the live pages before quoting any of it in the application.

---

## 1. The hackathon: Meta Global AI Developer Hackathon

### Where it lives
- Official page: <https://dev.meta.ai/events/global-hackathon>
- Applications and the listing run on **Cerebral Valley** (not Devpost or lablab): <https://cerebralvalley.ai/e/meta-ai-developer-hackathon> (markdown copy: <https://cerebralvalley.ai/e/meta-ai-developer-hackathon.md>)
- Organizers are Meta and Cerebral Valley. The partner inference providers are Baseten, Modal and Fireworks ([CV listing](https://cerebralvalley.ai/e/meta-ai-developer-hackathon.md)).
- The event is virtual and worldwide, free if you're selected, with a 10-day build ([Meta page](https://dev.meta.ai/events/global-hackathon)).

### Tracks and themes
Every project enters **one track** and targets one or both **themes** ([Meta page](https://dev.meta.ai/events/global-hackathon)):

| | What it says | Judged on |
|---|---|---|
| **Track 1: Indie developer** | "For individual builders and students." | "creativity, technical ambition, and whether it works" |
| Track 2: Startup | "For teams and founders building a real product." | "technical execution and whether it holds up in production" |
| Theme: Build for Your World | Meta's models in your own domain | — |
| **Theme: Push the Frontier** | "Use Meta's models to tackle challenges in software, robotics, manufacturing, energy, materials and beyond." | — |

**MIMIC enters the Indie track with the "Push the Frontier" theme.** Robotics is one of the domains that theme lists; it is not a sub-track of its own. Neither page formally defines "indie" (by team size, funding, etc.).

### Dates (ET, "subject to change at Meta's sole discretion")
Source: [Meta page](https://dev.meta.ai/events/global-hackathon), cross-checked with the [CV listing](https://cerebralvalley.ai/e/meta-ai-developer-hackathon.md).

| Milestone | When | IST (for the user) |
|---|---|---|
| Applications open (rolling review) | Oct 13, 2026, 9:00 AM ET | |
| **Application deadline** | **Oct 25, 2026, 11:59 PM ET**, or earlier if 20,000 spots fill | Oct 26, 9:29 AM ([Internshala](https://internshala.com/competitions/meta-global-ai-developer-hackathon-2026/)) |
| Acceptance notices | by Oct 26, 9:00 AM ET | |
| Kickoff livestream | Oct 26 (CV: "Oct 26 at 12:00 PM – Nov 4 at 9:00 PM EST") | |
| Workshops and Discord office hours | Oct 27 – Nov 4 | |
| **Submissions due** | **Nov 4, 2026, 9:00 PM ET** | Nov 5, 6:30 AM |
| Judging | Nov 4 – 8 | |
| Closing ceremony, live finals, winners | Nov 9 | |

The portal can close early once the cap is reached, so **apply early rather than on the 25th**.

### Prizes and credits
- $1,000,000 total "across two tracks". **No per-track or per-place split has been published** ([Meta page](https://dev.meta.ai/events/global-hackathon)).
- Partner credits for "select participants" ([CV listing](https://cerebralvalley.ai/e/meta-ai-developer-hackathon.md)):
  - Baseten: $100 plus 2M TPM for Meta open-weights models
  - Modal: $100
  - Fireworks: $25 plus a workshop
- **Unverified:** "$150 in Meta Model API credits" per selected participant. This appeared only in a search snippet of [Meta's X post](https://x.com/MetaforDevs/status/2110045152601633114) and on [resourify.com](https://resourify.com/resources/meta-api), not on the official page.

### Eligibility
- Worldwide, except people under sanctions or export controls, and anyone in Belarus, China, Russia, Ukraine, Syria, Crimea/Donetsk/Luhansk, Cuba, North Korea or Iran ([Meta page](https://dev.meta.ai/events/global-hackathon)).
- Staff of Meta and Cerebral Valley and their households are excluded, as are government-affiliated individuals.
- At most 20,000 selected applicants. Duplicate or false-identity applications can be disqualified.
- **Minimum age and team size are not stated.**
- The Meta Model API has its own geographic policy. It blocks Pakistan, the PRC and others. **Muse Image is blocked in India**, but Muse Spark and SAM 3.1 are not ([geographic policy](https://dev.meta.ai/legal/geographic-use-policy)). MIMIC uses neither Muse Image nor any other blocked model.

### How applications are selected
Selection uses **only the form answers**, scored on two **equally weighted** criteria ([Meta page](https://dev.meta.ai/events/global-hackathon)):
1. **Project idea:** "how clear and feasible your proposed project is, and how well it fits one of the two project themes."
2. **Technical skill:** "the technical skill shown in the AI project you describe, including what you built and the techniques you used."

GitHub, LinkedIn or shipped-product links are optional but help verify experience. Applications that meet the score cut-off are accepted automatically, up to the first 20,000. "Answers to questions 13 to 16 help us improve our developer programs and are not used in selection", so the form has at least 16 questions.

**The exact form questions are not public.** They sit behind a Cerebral Valley sign-in. [APPLICATION.md](APPLICATION.md) is drafted against the two published criteria, with blocks the user can paste into whatever the form asks.

### Models you can build with
Muse Spark series, Muse Image and SAM 3.1 via the Meta Model API, plus Meta open-weights models and Muse Code ([Meta page](https://dev.meta.ai/events/global-hackathon)). **No rule has been published that requires a specific Meta model.**

### Not published yet
"Official Rules will be published before the Hackathon begins on October 26, 2026" ([Meta page](https://dev.meta.ai/events/global-hackathon)). Until then these are unknown:
- submission requirements (video length, public repo, demo)
- final-judging weights and judges
- IP and licensing terms
- whether pre-existing code or hardware is allowed

A third-party article *guesses* at a 2–3 minute video, a public repo and a write-up ([genaimagazine](https://thegenaimagazine.com/meta-global-ai-developer-hackathon-ideas-prizes)). **These are not rules.** Plan for them anyway, and re-read the rules on Oct 26.

---

## 2. SAM 3.1

### What it is
- SAM 3 and SAM 3D were announced Nov 19, 2025 ([Meta newsroom](https://about.fb.com/news/2025/11/new-sam-models-detect-objects-create-3d-reconstructions/)). SAM 3 detects, segments and tracks objects in images and video. It takes short noun-phrase text prompts, image exemplars, points, boxes or masks. Its "promptable concept segmentation" returns **every instance** of a concept ([Meta AI blog](https://ai.meta.com/blog/segment-anything-model-3)).
- **SAM 3.1** came out on **Mar 27, 2026**. It adds *Object Multiplex*, shared memory for tracking many objects jointly ([blog](https://ai.meta.com/blog/segment-anything-model-3), [GitHub](https://github.com/facebookresearch/sam3)):
  - it tracks "up to **16 objects in a single forward pass**"
  - it runs at about 32 FPS on one H100 for medium object counts
  - the model has 848M parameters ([GitHub](https://github.com/facebookresearch/sam3))
- Known limits ([blog](https://ai.meta.com/blog/segment-anything-model-3)):
  - weak on fine-grained, out-of-domain concepts
  - no native support for long referring phrases; Meta suggests pairing it with an MLLM, which is exactly what Muse Spark does in MIMIC

### Access path A: the hosted Meta Model API (the plan)
- Model page: <https://dev.meta.ai/models/sam-3-1>. Docs: <https://dev.meta.ai/docs/sam/overview> and <https://dev.meta.ai/docs/sam/segmenting>.
- Call model **`sam-3.1`** with `POST https://api.meta.ai/v1/responses` (OpenAI Responses-compatible) and a Bearer key. Send one user message with an `input_text` noun phrase plus an `input_image` or `input_video`. Upload files with `POST /v1/files` and `purpose=user_data`.
  - The model page URL says "sam-3-1", so check which ID the API accepts.
- **The output is special-token text in `output_text`, not JSON.** Each frame gets a line with a box and a mask per object, and `metadata.mask_encoding: "one_bit"` makes masks smaller. Meta's `@meta-sam/parser` decodes it. Object identity is stable across frames ([overview](https://dev.meta.ai/docs/sam/overview)).
- Limits ([segmenting](https://dev.meta.ai/docs/sam/segmenting)):
  - up to 16 objects per frame and 15,000 frames (about 10 min) per request
  - MP4 or MOV with H.264, H.265 or MPEG-4; no WebM or VP9
  - **one concept per request:** "hand, cup" returns nothing, so send "hand" and "cup" separately
  - **text prompts only;** points, boxes and clicks work only with the open weights
- Pricing: **$0.20 per 1,000 video frames** and $2.50 per 1,000 images, with a 3,000 RPM limit ([pricing](https://dev.meta.ai/docs/pricing-rate-limits)). A 20 s clip at 30 fps is 600 frames, about $0.12 per concept, so hand plus three objects comes to about $0.48 per clip (our arithmetic).

### Access path B: open weights
- Code: <https://github.com/facebookresearch/sam3> under the SAM License. The checkpoints are **gated** on Hugging Face, so you must accept the terms first: <https://huggingface.co/facebook/sam3.1>.
- The 3.1 model card says there is **no Transformers integration**. It needs Python 3.12+, PyTorch 2.7+ and a **CUDA 12.6+ GPU**.
- **Apple Silicon:** unverified. One community thread got SAM 3 (not 3.1) running on an M-series Mac through Transformers main ([HF discussion](https://huggingface.co/facebook/sam3/discussions/11)). With 16 GB of RAM and a swap-prone Mac, **don't try it locally. Use the hosted API.**

### SAM 3D Body (hand pose)
- Single-image 3D body and hand mesh recovery, self-hosted only: [repo](https://github.com/facebookresearch/sam-3d-body), [paper](https://arxiv.org/abs/2602.15989).
- Its hand accuracy trails specialist models ([The Batch](https://www.deeplearning.ai/the-batch/metas-sam-3-image-segmentation-suite-analyzes-and-creates-3d-bodies-and-other-objects), secondary source).
- Not needed for MIMIC v1: grasp timing comes from the *object* moving under the hand, which masks alone give us (see `mimic/segment.py`).

---

## 3. Muse Spark

### What it is
- Muse Spark launched **Apr 8, 2026** as the first model from **Meta Superintelligence Labs**, with closed weights ([Fortune](https://www.fortune.com/2026/04/08/meta-unveils-muse-spark-mark-zuckerberg-ai-push)).
- Public API preview of 1.1 since **Jul 8, 2026** ([Meta blog](https://dev.meta.ai/resources/blog/build-with-muse-spark)).
- 1.2 and Muse Code came on Aug 5 with global access expanded ([Meta blog](https://dev.meta.ai/resources/blog/build-with-muse-code)).
- 1.3 arrived on Sep 2 ([secondary](https://propakistani.pk/2026/09/03/meta-launches-muse-spark-1-3-with-faster-coding-and-smarter-agents/); listed in the [model table](https://dev.meta.ai/docs/models.md)).

### Access and limits
- Sign up at dev.meta.ai and create a key. The API is **OpenAI SDK-compatible** at `https://api.meta.ai/v1` and also accepts the Anthropic Messages format ([blog](https://dev.meta.ai/resources/blog/build-with-muse-spark)).
- Model IDs: `muse-spark-1.3`, `-1.2` and `-1.1`, plus `-contributor` variants ([models](https://dev.meta.ai/docs/models.md)).
- Inputs: text, image, video, audio and PDF, with a **1,048,576-token** context ([models](https://dev.meta.ai/docs/models.md)).
- It supports tool calling, **structured output**, search grounding, and `reasoning_effort` from `minimal` to `xhigh`. That structured output means JSON Schema is reported only by a third-party catalog, so it is unverified ([catalog](https://catalog.empiriolabs.ai/models/muse-spark-1-1)).
- Pricing for Standard 1.1–1.3 is $1.25 in / $4.25 out per 1M tokens (cached input $0.15), with 3,000 RPM and 4M TPM per team ([pricing](https://dev.meta.ai/docs/pricing-rate-limits)). Reasoning tokens bill as output.
- **Contributor** mode is about 10× cheaper, but Meta may train on your data. **Never use it on demonstrators' videos.**

What MIMIC uses: `POST /v1/chat/completions` with `muse-spark-1.3`, a JSON-schema `response_format`, the segmented steps as text and up to four key frames as images (`mimic/writer.py`). The safety check's issues go back to it for repair, for at most two extra rounds. One clip costs roughly 3–8k input and 2–4k output tokens per round, about $0.02 or less (our estimate, unmeasured).

**Muse Voice Transcribe** (`muse-voice-transcribe-1.0`, $0.18 per audio hour) could later let a demonstrator narrate the clip ("now the red one goes in the bowl") ([models](https://dev.meta.ai/docs/models.md)).

---

## 4. Prior art, and how MIMIC differs

| Work | Venue | Lab | What it does | What it needs |
|---|---|---|---|---|
| **MimicPlay** ([arXiv](https://arxiv.org/abs/2302.12422), [site](https://mimic-play.github.io), [code](https://github.com/j96w/MimicPlay)) | CoRL 2023 (oral) | Stanford, NVIDIA, Georgia Tech, UT Austin, Caltech | Learns latent plans from human play video that guide a low-level visuomotor policy | ~10 min of human play **plus teleoperated robot demos** |
| **R+X** ([arXiv](https://arxiv.org/abs/2407.12957), [site](https://www.robot-learning.uk/r-plus-x)) | ICRA 2025 | Imperial College (Edward Johns) | A VLM retrieves relevant clips from long first-person video, then in-context imitation (KAT) executes the skill without training | A large pool of everyday human video and a robot arm |
| **OKAMI** ([arXiv](https://arxiv.org/abs/2410.11792), [site](https://ut-austin-rpl.github.io/OKAMI/)) | CoRL 2024 (oral) | UT Austin, NVIDIA | One RGB-D human video becomes a plan via object-aware retargeting; rollouts train closed-loop policies (79.2% success) | **RGB-D** video and a **humanoid** |
| **Vid2Robot** ([arXiv](https://arxiv.org/abs/2403.12943), [site](https://vid2robot.github.io)) | RSS 2024 | Google DeepMind, CMU, Toronto | An end-to-end policy conditioned on a human prompt video | A **large paired dataset** and Google's robots; no code |
| Phantom ([arXiv](https://arxiv.org/abs/2503.00779)) | CoRL 2025 | Stanford | Turns human video into robot data by inpainting the arm; zero-shot deploy | Human video only, then training |
| EgoMimic ([arXiv](https://arxiv.org/abs/2410.24221)) | 2024 | Georgia Tech | Co-trains on egocentric human and robot data | Project Aria glasses plus robot data |
| AR2-D2 ([arXiv](https://arxiv.org/abs/2306.13818)) | 2023 | UW (unverified) | An **iPhone AR app** records demos that then train a policy | iPhone, then training |
| ZeroMimic ([arXiv](https://arxiv.org/abs/2503.23877)) | ICRA 2025 | UPenn | Distills skills from EpicKitchens video | Web video and training |
| HOST ([arXiv](https://arxiv.org/abs/2607.20033), [news](https://techxplore.com/news/2026-08-robots-skills-video-seconds.html)) | 2026 | BIT, X Square, Tsinghua | One human video gives a skill at inference; 62% on unseen tasks | Two 6-axis arms, 3 cameras and a pretrained model |
| Skild AI S1 ([news](https://datanorth.ai/news/skild-ai-launches-s1)) | Aug 2026 | Skild AI | A closed foundation model prompted by one human video | Closed; no API or weights |

**Hardware context:** the SO-101 (Hugging Face LeRobot, 3D-printable) starts at about $100 in parts, and kits cost about $100–500 ([TechCrunch](https://techcrunch.com/2025/04/28/hugging-face-releases-a-3d-printed-robotic-arm-starting-at-100)).

**Consumer products:** the search found **no shipping app that turns one phone clip into a program for a cheap arm**. That is a negative search result, not proof that none exists.

### Where MIMIC is different
1. **No robot data, teleop or training.** MimicPlay and EgoMimic need robot demos, Vid2Robot a paired dataset, and Phantom and AR2-D2 a training run. MIMIC needs one clip and two hosted models.
2. **A monocular phone clip.** OKAMI needs RGB-D, EgoMimic needs Aria glasses, HOST needs three cameras.
3. **The output is a readable, editable program**, not network weights. It is a list of named fingertip waypoints a person can read, change, check again and share. The page has an "Edit JSON → Check again" loop.
4. **The model never sets a joint angle.** Muse Spark writes task-space waypoints. Deterministic code solves the inverse kinematics, replays the program in simulation at the arm's real 25 Hz step rate, and refuses it if any pose breaks a joint limit or any in-between step dips below the table. That check is HOTARU's gesture-compiler discipline. Muse Spark gets the issues back and repairs the program.
5. **A $200–300 printable arm** (SO-101 / Thenar) rather than humanoids or Franka-class arms.
6. **The corpus story:** anyone with a phone can become a paid ThenarLabs demonstrator, with no teleop rig.

### Where MIMIC is weaker (say so in the application)
- **Open-loop replay.** It won't recover if an object moves or slips mid-run. OKAMI, Phantom and HOST produce closed-loop policies.
- **It depends on calibration.** It assumes a top-down clip over a known mat and the table plane. Heights are guessed (the sample's are known, real clips default to 3 cm unless Muse Spark estimates them), and accuracy falls off with camera tilt.
- **Coarse grasps.** Top-down parallel-jaw grasps only. Yaw comes from the mask's long side, and there is no 6-DoF grasp or finger pose.
- **Simple tasks.** Pick-and-place and slides of rigid objects; no deformables, insertion or tools.
- **Same layout only.** The program replays positions; re-perceiving at run time would need a camera on the robot.
- **SO-101 limits.** Low payload and hobby-servo backlash.

---

## Could not verify
1. The exact application form questions (behind a sign-in).
2. The Official Rules: submission requirements, judging weights, judges, IP terms, and the rule on pre-existing code or hardware (due before Oct 26).
3. The per-track and per-place prize split.
4. Minimum age, team-size limits and a formal definition of "indie".
5. The $150 API credit per participant.
6. Whether using Meta models is mandatory.
7. SAM 3.1 on Apple Silicon, and the exact API model ID ("sam-3.1" vs "sam-3-1").
8. SAM 3.1 API file-size and resolution limits, and the exact token format of its output.
9. Muse Spark's maximum output tokens, video-input limits, and whether JSON-schema output is strict.
10. Venues for EgoMimic, AR2-D2 and Point Policy.
11. A public "Thenar" arm page: the research agent found none, so **link ThenarLabs' own page in the application**.

The raw notes these were condensed from are in the side-session notes folder (`mimic-research-raw.md`).
