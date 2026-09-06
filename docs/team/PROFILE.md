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

## 1a. Whole-team context (answered 2026-09-06)

- Core usable team overall: roughly **10 mentors, 20 students** (rough guess, "probably pretty
  close").
- **Mechanical is the largest subteam** and has the most dedicated mentors of any subteam
  (2-3). Software has comparatively fewer active mentors, but the trajectory matters more than
  the headcount here (next point).
- **Software's reputation has flipped.** Before Stephen joined, software was seen as a
  bottleneck/liability for the team. Over the last 2 years it's become seen as an opportunity
  instead. The plan should protect and extend that trajectory, not just treat software as "a
  subteam that needs students" in the abstract.
- There's real subsystem-level work students *can* do even though the vision pipeline is out
  of reach for a while — this matches the rung-ladder approach in the curriculum draft.
- **Team composition:** hosted by a private school that doesn't advertise the team well
  internally. Roughly **half the team is homeschoolers**, recruited outside the school's own
  student body, and — per the mentor's direct assessment — the homeschoolers tend to be the
  strongest contributors on the team. The school benefits optically from more of its own
  students joining but doesn't invest resources to make that happen, so school-driven
  recruitment can't be counted on. **Growth strategy should treat homeschool recruitment as a
  primary, not secondary, channel** — it's already outperforming the "official" pipeline.

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

## 2a. Mentor pipeline (answered 2026-09-06)

- **No formal mentor recruitment process.** Mentors come almost entirely through students —
  a student's parent happens to be a software engineer or works somewhere like L3Harris, and
  recruitment happens organically from that connection. This mirrors the recruitment story in
  §5a: the working channel is relational/word-of-mouth, not structured outreach, for both
  mentors and students.
- **Untapped resource: RIT (Rochester Institute of Technology) connection.** One of the team's
  lead mentors is senior in RIT's entrepreneurship program (startup investing + mentoring
  background). This is a live bridge to a local college that isn't yet described as being used
  for team growth — worth exploring deliberately: RIT engineering/CS students as near-mentors
  or occasional helpers, RIT's own outreach/volunteering programs, or simply asking this mentor
  who else at RIT might want to get involved. Given mentor bandwidth is the team's tightest
  constraint (§2), a college-student mentor pipeline (even informal, even just a few hours/
  month per person) could matter more than any single new recruitment tactic.
- **Closest thing to a near-mentor today:** an autonomous-lead student, strong on leadership
  and problem-solving, weaker on raw technical depth (growing their technical ability is
  explicitly on the mentor's to-do list). They design autonomous routines using the existing
  AutoPilot-based tooling and are independently investigating alternatives (Choreo) — real
  initiative, not just following instructions. Not yet a general software captain, but a
  plausible one to grow deliberately rather than a role to fill externally.

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
- **Deliberate tradeoff, not an oversight:** student commits mostly come from a shared
  `Student`/`Finney Student` account rather than individual logins (2027Robot: `Student` — 20
  commits, undifferentiated). This is intentional — students are on shared school laptops with
  low general tech fluency, and the setup cost of an individual GitHub account + git config +
  VS Code auth, redone every time a student switches laptops, is a real onboarding tax the team
  has decided isn't worth paying. The tradeoff is losing per-student attribution/growth
  tracking from the repo. Any growth plan should treat this as a constraint to design around
  (e.g., attribution via commit message trailers, a lightweight external log, or in-person
  tracking) rather than a gap to close by pushing individual accounts.
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
  based on what they've actually done, or to show growth over time. Accepted tradeoff
  against onboarding friction on shared school laptops; solve around it, don't reverse it.

## 5. Stated goals, in priority order (refined 2026-09-06)

1. **More software students overall, with deeper technical ability.** Explicitly the top
   priority — growth in headcount and growth in depth are treated as one goal, not two.
2. **Scale up leadership/confidence-building to more students.** Already happening at small
   scale (see the autonomous-lead student in §2a); the goal is the same mentoring approach
   at a larger scale, which the mentor explicitly ties to needing more mentors (§2a's RIT
   lead is the obvious first thing to pull on).
3. Personally keep pushing the technical ceiling upward (the mentor's own R&D — vision,
   tooling, etc.), on the theory that this also improves competition results both directly and
   by giving students more advanced subsystem/autonomous work to grow into.
4. Better competition results — treated as a downstream effect of 1-3, not a separate lever to
   pull directly.
5. Less dependence on the mentor specifically — implied throughout, not named outright as a
   top priority, but structurally what closing the mentor-bottleneck (§2a) and building a
   near-mentor pipeline (§2a) would produce.

Net: this is a **student depth + mentor capacity plan**, not primarily a marketing/headcount
plan. Recruitment (§5a) matters, but mainly as a way to get more raw material for the deeper
goal of building technical depth and leadership — a growth plan that adds students without a
way to grow their depth would miss the actual priority.

## 5a. Recruitment channels tried so far (answered 2026-09-06)

- School side: in-school announcements + a small demo table at events like homecoming.
  Stated as "not really very effective."
- **Best channel today is word of mouth** — a student bringing a friend. Some homeschoolers
  already self-select in via word of mouth within homeschool circles, unprompted.
- **Nothing structured has been tried in the homeschool community** — no outreach email to
  homeschool groups/co-ops yet. The mentor's own instinct, stated directly: "we could go in and
  do an email or two to a couple of these homeschool groups and get a ton of kids interested."
  This is a cheap, untried, high-confidence lever — should rank near the top of any plan given
  it's low-effort and the mentor already believes it'll work, versus school-side channels that
  have been tried and underperformed.
- Caveat: mentor is new to the recruitment side of team ops and has only vague knowledge of
  history here — treat this section as directionally right, not exhaustive. Whoever has run
  recruitment longer (or the outreach/business subteam, if one exists) may have more detail or
  have already tried homeschool outreach without it sticking.

## 6. Open questions

Answered via Q&A on 2026-09-06 — see §1a (team size/context), §5a (recruitment tried), §2a
(mentor pipeline, near-mentor candidate), §5 (success priorities).

Still genuinely open, not yet asked or answered:

- ~~**School support**~~ — answered 2026-09-06: the school provides physical space (a room +
  workshop area) and nothing else — no paid staff time, no course credit mentioned, and
  (consistent with §1a) minimal promotion. Confirms the school is a facilities landlord, not a
  program partner; any growth lever involving the school should assume space-only support and
  budget accordingly. No feeder pipeline (FLL/FTC, middle-school program) mentioned — worth a
  quick follow-up if useful, but not asked yet.
- **Competition results/history:** is there a specific technical weakness (reliability,
  autonomous consistency, driver practice) actually costing matches, separate from the
  team-growth question? Lower priority per §5 (results are treated as downstream of student
  depth), but still useful if there's a specific fire to put out.
- **Time budget:** how many hours/week do students realistically have, in-season vs. offseason?
  How long is build season for this team? Matters directly for pacing the onboarding curriculum
  (§ referenced in `onboarding/CURRICULUM.md`) — a rung sized for a 2-hour weekly meeting looks
  different than one sized for daily after-school access.

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
