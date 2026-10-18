---
name: MIMIC
description: Film it once, the arm repeats it. A movement score of what the person did beside what the arm will do.
colors:
  paper: "#f4f5f2"
  sheet: "#fbfbf9"
  well: "#eceee9"
  rule: "#d9dcd6"
  staff: "#b9bdb7"
  field: "#8d9296"
  ink: "#121416"
  ink-2: "#41464b"
  ink-3: "#62686d"
  robot: "#2747c9"
  robot-tint: "#e3e8fa"
  robot-ink: "#1a3297"
  issue: "#b02e19"
  issue-tint: "#fbe7e2"
  issue-ink: "#8e2412"
  hand: "#8a5a3c"
typography:
  display:
    fontFamily: "Schibsted Grotesk, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Schibsted Grotesk, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Schibsted Grotesk, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Schibsted Grotesk, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0.06em"
  data:
    fontFamily: "Spline Sans Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  score:
    fontFamily: "Spline Sans Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "12px"
    fontWeight: 400
    fontFeature: "tnum"
  voice:
    fontFamily: "Schibsted Grotesk, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    letterSpacing: "0.06em"
  wordmark:
    fontFamily: "Schibsted Grotesk, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 700
    letterSpacing: "0.14em"
rounded:
  swatch: "2px"
  row: "4px"
  control: "6px"
  sheet: "10px"
  pill: "99px"
spacing:
  hair: "4px"
  xs: "8px"
  sm: "10px"
  md: "12px"
  lg: "16px"
  gutter: "20px"
components:
  button:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "34px"
    padding: "0 13px"
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    height: "34px"
    padding: "0 13px"
  button-run:
    backgroundColor: "{colors.robot}"
    textColor: "#ffffff"
    rounded: "{rounded.control}"
    height: "34px"
    padding: "0 13px"
  button-run-hover:
    backgroundColor: "{colors.robot-ink}"
  button-halt:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.issue}"
    rounded: "{rounded.control}"
    height: "34px"
    padding: "0 13px"
  button-halt-hover:
    backgroundColor: "{colors.issue-tint}"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.control}"
    height: "28px"
    padding: "0 8px"
  button-quiet-hover:
    backgroundColor: "{colors.well}"
    textColor: "{colors.ink}"
  field:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    height: "34px"
    padding: "0 10px"
  verdict-safe:
    backgroundColor: "{colors.robot-tint}"
    textColor: "{colors.robot-ink}"
    rounded: "{rounded.control}"
    padding: "11px 12px"
  verdict-unsafe:
    backgroundColor: "{colors.issue-tint}"
    textColor: "{colors.issue-ink}"
    rounded: "{rounded.control}"
    padding: "11px 12px"
  row-selected:
    backgroundColor: "{colors.robot-tint}"
    rounded: "{rounded.row}"
  row-flagged:
    backgroundColor: "{colors.issue-tint}"
    rounded: "{rounded.row}"
  tag:
    textColor: "{colors.ink-2}"
    typography: "{typography.data}"
    rounded: "{rounded.pill}"
    padding: "2px 7px"
  now-pill:
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "5px 10px"
---

# Design System: MIMIC

## Overview

**Creative North Star: "The Movement Score"**

MIMIC is a single sheet of cool staff paper, notated in ink. A phone clip is written down the way Labanotation writes a dance: a vertical staff where time runs up, the person on the left of a heavy centre line and the arm on the right, so the two performances can be read against each other at one glance. Everything else on the sheet (the clip with its tracked overlay, the 3-D replay, the steps, the program) is a margin note to that score, and every note carries its proof in millimetres and seconds.

The world has exactly three voices. Ink black is the notation itself: text, staff lines, the person's marks. Ink blue is the robot's voice and nothing else: the arm's lane, the gripper, the replay's fingertip path, the "safe to run" state, the Run on arm button. Vermilion appears only when something is wrong. Each tracked object adds one colour ribbon that it keeps everywhere it appears (video outline, name plate, staff block, 3-D table), and those ribbons are data, not chrome. Density is that of a working instrument: 14px body, 12px data, hairline rules between regions, no decoration that does not carry information.

The sheet is calm at rest and moves only to report: notes ink in once when a score is written, a spinner turns while the server works, and the two playheads travel the staff together. It refuses the category default of three equal dark panels of video, JSON and 3-D.

**Key Characteristics:**
- One ruled light sheet with hairline region dividers, not a grid of floating cards.
- Ink for notation, ink blue only for the robot, vermilion only for issues.
- One colour ribbon per tracked object, identical on video, staff and table.
- Labanotation level shading for height: solid low, dotted middle, hatched high.
- Every claim beside its measurement, set in tabular mono.
- Rank from weight, case and colour, not from large type.

## Colors

A near-neutral graphite-on-paper sheet with a faint green-grey cast, carrying one saturated blue for the machine and one vermilion for faults.

### Primary
- **Robot Ink Blue** (robot): the arm's voice. The ARM column label, the arm's playhead and end line, gripper-closed marks, the ARM subtitle and lane names, the planned fingertip path in 3-D, the grip pads on the 3-D arm's fingers, "grip" in the waypoint list, the live "On the arm" pill, the robot clock, focus rings, the text caret, the drag-over border, and the Run on arm button.
- **Robot Tint** (robot-tint): the selected row in Steps and Program, text selection, and the background of the "Safe to run" verdict.
- **Robot Deep** (robot-ink): text on Robot Tint and the Run on arm hover.

### Secondary
- **Fault Vermilion** (issue): the Stop button when it can act, the "not safe to run" count in the Steps header. Nothing decorative is ever this colour.
- **Fault Wash** (issue-tint): the unsafe verdict, a flagged waypoint row, the error message strip, the Stop hover.
- **Fault Deep** (issue-ink): text on Fault Wash (verdict, error strip, a waypoint's reason line). It is currently hard-coded in the stylesheet rather than declared on `:root`; it is still a system colour.

### Tertiary
- **Hand Umber** (hand): the person's hand, wherever it is drawn: its dashed outline on the video, its lane and holding brackets on the staff, its hook glyph at the staff foot. It is the person's counterpart to Robot Ink Blue.

### Neutral
- **Paper** (paper): the page behind the sheet, the top bar (88% with blur), and text on the ink primary button.
- **Sheet** (sheet): the staff paper itself, button faces, field faces, the fill inside dotted and hatched level patterns.
- **Well** (well): recessed surfaces inside the sheet: the clip stage, the 3-D viewport and its desk and fog, the JSON editor, row hover.
- **Rule** (rule): every hairline: region dividers, list row separators, lane dividers on the staff, the mat's centimetre grid in 3-D.
- **Staff** (staff): heavier structural greys: button borders, the staff's outer lines, the ties between your pick and the arm's grip, the dashed drop zone, scrollbar thumbs, the idle status dot.
- **Ink** (ink): all primary text, the staff's centre and starting lines, notation outlines, the person's playhead, the primary button.
- **Ink Second** (ink-2): secondary text: field labels, the key, transport times, summaries' supporting lines.
- **Ink Third** (ink-3): tertiary text: region asides, waypoint numbers, verbs, proof lines, time ticks, footer.

### Object ribbons (data colours)
Tracked objects take their colour from the pipeline by name (red, orange, yellow, green, teal, blue, purple, pink, magenta, with a grey fallback). They are rendered at full strength on staff blocks, name-plate swatches and 3-D meshes, at about 19% alpha as the fill of a video outline, and never as interface colour.

### Named Rules
**The Three Voices Rule.** Ink is the notation, ink blue is the robot, vermilion is a fault. Blue is otherwise allowed only for the sheet's own attention states (focus ring, caret, text selection, drop target, the selected row, links), which are the machine listening; it never colours the person's data or decoration. If nothing is wrong, nothing is vermilion.

**The One Ribbon Rule.** An object has exactly one colour, and it is the same on the video, the score, the step plate and the 3-D table. Never recolour an object per view or per state; state is shown by dimming (28% opacity) or by row tint, never by changing the ribbon.

## Typography

**Display Font:** Schibsted Grotesk (with system-ui, sans-serif)
**Body Font:** Schibsted Grotesk (with system-ui, sans-serif)
**Label/Mono Font:** Spline Sans Mono (with ui-monospace, SF Mono, Menlo, monospace)

**Character:** A plain, slightly newsprint grotesk for words and a narrow technical mono for every measurement; the pairing reads like a printed score with its timings pencilled in.

### Hierarchy
- **Display** (600, 22px, -0.01em, balanced wrap): the empty-state invitation on the clip stage ("Show it once."). The largest type in the world.
- **Headline** (500, 17px, -0.01em, balanced wrap): the one-sentence summary of what was notated, above the steps.
- **Body** (400, 14px, 1.5): step descriptions, verdict text, buttons (500), fields. Supporting paragraphs cap at 44ch.
- **Label** (600, 12px, 0.06em, uppercase): region names (Clip, Score, Replay, Steps, Program) and the verbs in step and waypoint rows (pick, carry, place, grip). Lane names on the staff are sentence-case 500 12px in Ink Second (Robot Ink Blue on the arm's side), not uppercase.
- **Data** (Spline Sans Mono 400, 12px, tabular numerals): every millimetre, second, resolution, waypoint index and coordinate. Score ticks stay at 12px in Ink Third.
- **Voice** (700, 14px, 0.06em): YOU and ARM over the two halves of the score only, Ink and Robot Ink Blue, each with a 12px 500 subtitle beneath ("what the clip shows", "what it will do").
- **Wordmark** (700, 17px, 0.14em): MIMIC in the top bar only.

### Named Rules
**The One Data Size Rule.** Measurements are 12px mono everywhere; importance comes from weight, case, colour or bold, never from making a number bigger. 12px is also the floor: nothing on the sheet, the SVG score included, is set smaller.

**The Measured Claim Rule.** A step, verdict or score always shows its number in mono beside the words (`312 mm in 1.40 s`, `within 2 mm and 100 ms`). A claim without its measurement does not ship.

## Layout

One sheet, max 1680px wide (the footer shares the measure), centred with a 20px gutter (16px on phones), 18px below the top bar. Inside, a five-region grid with no gaps, divided only by 1px Rule hairlines:

- **Wide (above 1180px):** three columns at 1.05fr / 0.78fr (min 360px) / 1fr. Row one is Clip, Score, Replay; row two is Steps (under Clip and Score) and Program (under Replay). The score is the centre column, wide enough for its voices and lane names, and runs the full height of row one (420px minimum).
- **Medium (760 to 1180px):** two columns, 1fr / 0.75fr (min 330px). Clip and Replay stack on the left and the score spans both rows on the right; Steps and Program run full width below.
- **Narrow (below 760px):** one column, ordered Clip, Replay, Score, Steps, Program: you, then the arm copying you, then the detail. The score keeps a 440px minimum height. Step rows restack to plate and time on one line, verb, then description.

Regions pad 14px 16px 16px (12px 12px 14px on phones). Each region opens with a head of 28px minimum height and 10px below it. Internal spacing runs on 4 / 8 / 10 / 12 / 16 / 20px; row padding is tight (8px 6px for steps, 6px 4px for waypoints). The clip stage is 16:9, the replay viewport 4:3. Under the clip, the "What's in the clip" prompt spans its own row and Tracker and Program writer sit side by side beneath it (an 8px two-column grid).

**The Margin Note Rule.** The score sits in the middle and everything else is placed relative to it. A new panel joins the sheet as another hairline-divided region, never as a separate card floating beside it.

## Elevation & Depth

The system is flat paper. The sheet carries the only shadow, a single near-invisible lift (1px, 7% ink) that separates it from the page. Depth inside the sheet is tonal: Well recesses the clip, viewport and editor; Robot Tint and Fault Wash raise selected or flagged rows. Floating labels over media (the working strip, the "now" pill, the top bar) use a translucent sheet or paper with an 8 to 10px backdrop blur so the video or 3-D shows through; that is the only glass in the world. The 3-D replay is the one place with real light: ACES filmic tone mapping (exposure 1.05), soft studio reflections from a room environment, a hemisphere fill and one soft-shadowing sun, and a radial contact-shadow pool (Ink at 55% fading to nothing) under the arm's base and every object so nothing reads as floating. The desk is Well and is fogged into Well so it has no horizon; the mat is Sheet, ruled every centimetre in Rule with an Ink border, like the score.

### Shadow Vocabulary
- **Sheet lift** (`box-shadow: 0 1px 2px rgba(18, 20, 22, .07)`): the sheet only.
- **Field focus** (`box-shadow: 0 0 0 3px color-mix(in srgb, var(--robot) 18%, transparent)`): text fields, selects and the JSON editor on focus, with the border turning Robot Ink Blue.

### Named Rules
**The Flat Sheet Rule.** Nothing inside the sheet casts a shadow. Rows, verdicts and pills separate by tint, hairline or blur, never by elevation.

## Shapes

Corners are gently curved and consistent: 6px on every control, stage, viewport, verdict and field; 10px on the sheet; 4px on list rows and focus outlines; 2px on object swatches and gripper marks; fully round (99px) on tags, the "now" pill, scrollbar thumbs and the status dot. Borders are 1px; the drop zone alone uses a 1.5px dash. Inside the score, notation is drawn square-ended: carry blocks are plain rectangles with a 1px ink outline, a hook marks a pick, an open ring marks a put-down, a slanted stroke marks a turn, and height is filled solid (low, at or below 25mm), dotted (middle, below 55mm) or 45-degree hatched (high).

## Components

### Buttons
Quiet, paper-faced and squarely tactile; they press down 1px rather than glow.
- **Shape:** gently curved (6px), 34px high, 0 13px padding, 500 weight 14px, icon gap 7px.
- **Default:** Sheet face, Staff border, Ink text. Hover darkens the border to Ink Third.
- **Primary:** Ink face, Paper text. Used for Upload and Check again: the person's own actions.
- **Run:** Robot Ink Blue face, white text, Robot Deep on hover. The only filled blue control; it sits directly under the safety verdict and is disabled until the check passes.
- **Halt:** Staff border and Ink Second text while idle; Fault Vermilion border and text once it can act, Fault Wash on hover.
- **Quiet:** borderless, transparent, 28px high, 0 8px; Well on hover. Used for Edit JSON and Download.
- **States:** active presses 1px down (`.12s`); disabled drops to 45% opacity with a not-allowed cursor; busy spins its icon.

### Chips
- **Tag:** round outline in Staff, Ink Second 12px text, 2px 7px. Marks provenance ("synthetic clip").
- **Now pill:** round, translucent Sheet with 8px blur and a Rule border, 12px 500, single line with ellipsis, floating top-left of the 3-D view. Turns Robot Ink Blue (text and a 35% blue border) while the real arm runs.

### Cards / Containers
- **Corner Style:** the sheet at 10px; regions inside it have no corners of their own.
- **Background:** Sheet, with Well for recessed media.
- **Shadow Strategy:** see Elevation: the sheet lift only.
- **Border:** 1px Rule around the sheet and between regions.
- **Internal Padding:** 14px 16px 16px per region.

### Inputs / Fields
- **Style:** Sheet face, 1px Field border (`#8d9296`, ~3:1 on the sheet so the control edge meets WCAG 1.4.11), 6px, 34px high, 0 10px, body type. Labels sit above in Ink Second 12px with a 4px gap.
- **Focus:** border to Robot Ink Blue plus the 3px 18% blue ring; no outline.
- **JSON editor:** Well face, 12px mono at 1.55, 360px minimum height, vertical resize, same focus treatment.
- **Disabled options:** native disabled state for trackers and writers the server lacks.

### Navigation
A single sticky top bar: Paper at 88% with a 10px blur and a Rule bottom hairline, 10px 20px padding. The mark and wordmark sit left with "by ThenarLabs" in Ink Third 12px; a status line with a 7px dot (Staff idle, Robot Ink Blue when the server answers) and the two entry actions (Try the sample clip, Upload a clip) sit right. On phones the credit and status hide and button labels shorten.

### Movement Score (signature)
The heart of the system: an SVG staff where time runs up from a doubled ink starting line. A 1.4px Ink centre line divides YOU (left: a Hand Umber lane, then one lane per carried object) from ARM (right: holds, height, grip). Lanes are divided by Rule hairlines, the outer staff lines are Staff, and second ticks in 12px mono run down both edges. Each carry is a ribbon-coloured block whose length is its duration; the arm's height lane uses the solid, dotted and hatched shading; gripper-closed is a solid blue bar on a Staff hairline. Dashed Staff ties join your pick and place to the arm's grip and release. Two playheads (Ink for you, Robot Ink Blue for the arm) move with the shared clock; dragging the left half scrubs the clip and the right half scrubs the replay. Selecting a step dims every unrelated block to 28%. When a new score is written, the notes ink in upward over 900ms with the house ease (`clip-path` reveal), once.

The score is labelled like a printed score. YOU and ARM (Voice type) head the two halves with their subtitles; each lane is named at the foot under a small mark (the hand's hook in Hand Umber, an object's ribbon swatch, and for the arm a Sheet swatch for holds, a hatched one for height, a solid blue one for grip), long names breaking onto two lines ("red / block"). Lane names are hand, then each object, on your side; holds, height, grip on the arm's. Before any run the staff draws a ghost preview of a two-carry score at 16% opacity with "Your score is written here" in 14px Ink Second at its centre, so the empty state already teaches the notation. Under the staff, the key sits above a Rule hairline in a two-column legend (mark, then 12px Ink Second label): low, middle, high, picked up, put down, turned, gripper closed, you to arm.

### Replay (3-D arm)
A procedural SO-101 built from its parts at the program's real link lengths, so the fingertip lands where the waypoints say. Printed PLA brackets are an off-white physical material (`#f1efe9`, roughness .58, a light clearcoat); servo housings are near-black (`#18191b`) with brushed aluminium output horns (`#c9cdd1`, metalness .9) on every joint axis; the base plate is a pale grey; the only colour on the arm is the pair of Robot Ink Blue grip pads on the fingers' inside faces. Objects are matte blocks or lathe-turned bowls in their ribbon. The planned fingertip path is a Robot Ink Blue line at 55%. The camera looks from the robot's right so the base and the mat sit at the same distance, steps back on narrow screens, and orbits by drag only (no zoom, no pan; touch scrolls the page). Motion eases in and out of each move (smoothstep) and interpolates between the 25 Hz samples; between runs the arm holds its rest pose. The "now" pill names the current move.

### First Visit
A visitor with no saved run never meets a blank sheet: once the server answers, the sample clip loads and notates on its own. A returning visitor gets their last run back. The drop zone and its "Show it once." invitation stay up only if the server is unreachable or the sample fails.

### Step and Waypoint Rows
Hairline-separated list rows on a 4px corner. Steps run a four-column grid (object plate, verb label, description with a mono proof line beneath, right-aligned mono time). Waypoints run index, label with grip verb, right-aligned mono coordinates. Hover is Well; the current or selected row is Robot Tint; a waypoint that fails the check is Fault Wash with its reason in Fault Deep beneath.

### Safety Verdict
A tinted block directly above Run on arm with an icon, a bold one-line verdict and its numbers: Robot Tint and Robot Deep with a check when safe, Fault Wash and Fault Deep with an alert and a list of issues when not. Under an unsafe verdict, a note in Ink Third says running is locked.

### Name Plate (video overlay)
A small 19px plate above each tracked outline: translucent Sheet (92%), a hairline ink border at 14%, a 9px ribbon square and the label in 600 12px Ink. Plates step below or above an outline rather than stack on each other. Objects are outlined at 2px in their ribbon with a light fill; the hand is a 1.6px dashed Hand Umber outline; a carried object's path is a 5/5 dashed ribbon line with a ring at the pick and a dot at the place.

## Do's and Don'ts

### Do:
- **Do** keep Robot Ink Blue (#2747c9) for the arm, its states and the sheet's attention states (focus, selection, drop target), and Fault Vermilion (#b02e19) for faults only.
- **Do** give every tracked object one ribbon and use it identically on video, score, step plate and 3-D table.
- **Do** set every measurement in Spline Sans Mono 12px with tabular numerals, beside the words it proves.
- **Do** place any action that moves the real arm directly under the verdict that permits it, and disable it until the check passes.
- **Do** divide new regions with 1px Rule hairlines inside the one sheet, and recess media in Well.
- **Do** show height with Labanotation level shading (solid low, dotted middle, hatched high) wherever height is drawn.
- **Do** use the house ease (`cubic-bezier(.16, 1, .3, 1)`) for state changes at 0.12 to 0.2s, and let `prefers-reduced-motion` stop all motion.
- **Do** keep any border that alone identifies a control at 3:1 or better against its surface (WCAG AA is the product's floor).

### Don't:
- **Don't** split the sheet into three equal dark panels of video, JSON and 3-D; that is the category default this world refuses.
- **Don't** use blue for the person's marks, an object's ribbon chrome, or a decorative fill.
- **Don't** recolour an object to show state; dim it or tint its row instead.
- **Don't** enlarge numbers to rank them; use weight, case, bold or colour.
- **Don't** add shadows inside the sheet or float cards over it.
- **Don't** add a dark theme by inverting tokens; the world is light staff paper, and a dark variant would need its own pass.
