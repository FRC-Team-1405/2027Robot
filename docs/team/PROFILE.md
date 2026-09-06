# Team Profile — FRC Team 1405, Charles Finney Falcons (New York)

Working model of the team's structure, capacity, and constraints, built to support growth
planning. Grounded in evidence from the `2026Robot` and `2027Robot` repos where possible;
everything else is stated by Stephen (software mentor) directly or flagged as an open question.

Last built: 2026-09-06.

## 1. Team identity

- FRC Team 1405, "Falcons," Charles Finney School, New York.
- Software mentor (this repo's primary author) is deeply hands-on: writes architecture,
  builds internal tooling, and is actively experimenting with AI-agent-assisted development
  (see §4).

## 2. Mentor capacity (stated + evidence)

- **A handful of mentors are actively leading** — pushing curriculum, structure, and team
  building forward.
- **A second handful are "on and off"** — they show up intermittently and help individual
  students one-on-one, but aren't driving leadership or team-building.
- Git evidence (2026Robot, full season, Apr 2025–May 2026, 321 commits):
  - `Stephen Cerbone` — 141 commits (44%)
  - `Chris McDonald` — 7 commits
  - No other clearly-mentor accounts appear in the log — student and mentor contribution
    are hard to tell apart from git alone once students are committing directly.
- **Implication:** software mentorship capacity is concentrated in ~1 lead + a thin bench of
  occasional helpers. This is a bus-factor risk (see §4) and also means mentor time is the
  scarce resource any growth plan has to budget carefully — new initiatives that require
  *more* sustained mentor hours are less likely to survive than ones that are self-serve or
  front-loaded (built once, reused every year).

## 3. Student pipeline (stated + evidence)

- Stated: "a handful of students every year," maybe two are decent at basic programming,
  none are very competent programmers — expected, given they're in high school.
- Git evidence (2026Robot season):
  - `Dalton` — 85 commits (a strong, sustained contributor that season)
  - `Finney Student` (shared/generic account) — 48 commits
  - `Dylan Wilson` — 16, `GraceEK18` — 13, `reclaimernessie` — 4, `Aiden Richards` — 4,
    `Grace` — 1, `Andrew` — 1
  - This is a classic power-law distribution: one strong student, a small second tier,
    then a long tail of students who touched the code a handful of times.
- **Notable gap:** student commits mostly come from a shared `Student`/`Finney Student`
  account rather than individual logins (2027Robot: `Student` — 20 commits, undifferentiated).
  There's currently no way to reconstruct *which* student did what, or track an individual's
  growth over a season from the repo alone. If part of the growth goal is showing students
  (and colleges/parents/sponsors) a track record of their own progress, this is a fixable gap —
  worth each student committing under their own name/account.
- 2027Robot commit activity has gone quiet for everyone except Stephen and his AI-agent
  account since late May 2026 (offseason) — consistent with a normal summer lull, but also
  the point where a team risks losing the momentum/attachment built during build season if
  there's no offseason on-ramp.

## 4. Technical program assessment

**Strengths (unusual for a small team this size):**
- Full AdvantageKit IO-layer architecture (hardware/sim/replay separation) — this is a
  "veteran team" pattern, not a rookie one.
- Deterministic log replay used for *debugging methodology*, not just telemetry viewing —
  `docs/vision-testing-protocol.md`, feature-switch-gated A/B comparisons.
- Custom internal tooling built and actively maintained: `tools/logbench` (metric/composite
  scoring over match logs, web UI), `tools/camera-calibration`, `tools/vision-analyzer` —
  i.e., the mentor is building *tools for coaching the robot*, not just the robot.
- Real documentation culture: `SubsystemWritingGuide.md`, `HowToTuneASwerveDrive.md`,
  `CompetitionChecklist.md`, an offseason project backlog (`OffseasonProjects.md`) with
  ChiefDelphi citations and completed/pending tracking. This is genuine investment in
  making the program teachable, not just functional.
- Mentor is actively using AI coding agents (Claude Code) as part of the workflow already
  (see the `PiClaw` commit trail, dictated "ai: ..." commit messages) — the team is ahead
  of most FRC programs on this axis, and the user is clearly comfortable directing agentic
  tools, which is why this exercise (pointing Fable at team growth) is a natural extension.

**Limitations / risks this creates:**
- **Bus factor.** The architecture's sophistication depends on one person's mental model.
  If Stephen is unavailable for a stretch, there may be no one else who can safely modify
  `Vision.java`'s filter pipeline, the replay boundary, or the logbench internals.
- **Skill-floor / skill-ceiling gap.** The codebase assumes comfort with interfaces,
  dependency injection (`FooIO`/`FooIOTalonFX`/`FooIOSim`), annotation processors, and
  A/B experimental design. That's a steep on-ramp for a student whose only prior exposure
  is a semester of intro programming. Guides exist, but they're written *for* someone who
  already thinks in these abstractions, more onboarding-checklist than tutorial-from-zero.
  This likely explains the power-law contribution curve in §3: the gap between "can follow
  a guide to add a button binding" and "can reason about the vision filter pipeline" is
  large, and there isn't yet a visible rung-by-rung ladder between them.
- **Mentor time is the bottleneck for closing that gap.** Sophisticated architecture
  requires sophisticated teaching to transfer, and the mentors who could do that teaching
  are the same ones being asked to lead everything else.
- **No student-attributable history**, per §3 — makes it harder to mentor individuals
  based on what they've actually done, or to show growth over time.

## 5. Stated goals

- Improve the software program generally.
- Attract more students to the program (recruiting/pipeline growth).
- Underlying, implied goal: build a team that's less dependent on one or two people —
  durable across mentor and student turnover.

## 6. Open questions (not derivable from the repo — needed for a real plan)

These are the load-bearing unknowns. Worth answering before or during the Fable run,
either by the user directly or by having the agent ask rather than assume:

- **Team-wide context:** total team size (all subteams, not just software)? Is software
  seen as a bottleneck, a strength, or invisible to the rest of the team/school?
- **School support:** does Charles Finney give the team a classroom/lab, a course credit,
  release time, funding? Is there a feeder pipeline (a middle-school program, a robotics
  elective, FLL/FTC teams that funnel into FRC)?
- **Recruitment channels tried already:** what's been tried to attract students (announcements,
  clubs fair, teacher referrals, alumni outreach) and what happened?
- **Competition results/history:** how has the team performed? Is there a specific technical
  weakness (e.g., reliability, autonomous, driver practice) that's actually costing matches,
  separate from the "grow the team" question?
- **Time budget:** how many hours/week do students realistically have, in-season vs.
  off-season? How many weeks is "build season" vs. "offseason" for this team?
- **Mentor pipeline:** where do mentors come from (parents, alumni, local engineers)? Is
  there a path to convert an "on-and-off" mentor into a more consistent one, or a strong
  senior student into a near-mentor/captain role?
- **What "success" looks like in 1 year vs. 3 years** — more students, better retention,
  less mentor dependency, competition results, or some mix, in what priority order?

## 7. Constraints for any plan built from this profile

- Solutions should be **front-loaded, not recurring** where possible — curriculum,
  templates, and checklists that get built once and reused, rather than things that need
  a mentor's live attention every week.
- Solutions should **close the skill-floor gap incrementally** — a ladder of small, real
  contributions a first-year student can make and see land, rather than expecting a jump
  straight to the existing architecture's abstraction level.
- Anything proposed should be honest about **mentor bandwidth being the scarcest resource** —
  prefer plans that reduce mentor load over time (even if they cost mentor time up front)
  over plans that add a permanent new mentor obligation.
