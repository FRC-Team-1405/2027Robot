# Growth Plan — FRC 1405 Software Program

Built from `docs/team/PROFILE.md` (treat that as ground truth for capacity/pipeline claims).
Organizing principle, per the profile's §7 constraints: **mentor hours are the budget.**
Every item below is priced in mentor time, and anything recurring had to justify itself.

Drafted 2026-09-06. Everything here is a draft for the mentor to edit and act on — nothing
has been sent, posted, or committed on your behalf.

---

## Top 3 recommendations (if you skim nothing else)

1. **Adopt the onboarding ladder and individual commit attribution together, now, before
   kickoff.** `docs/team/onboarding/CURRICULUM.md` is a 12-rung sequence of real
   contributions to this codebase, each ending in a commit under the student's own GitHub
   account. It's self-serve by design: a student can run rungs 1–5 with no mentor in the
   room. This is the single cheapest attack on all three stated goals at once (skill
   floor, bus factor, visible student growth). Cost: ~2 hours of mentor review of the
   curriculum + one meeting to set up student GitHub accounts. Recurring cost: ~0.

2. **Run a 6-week fall on-ramp using the simulator and last year's robot, and make it the
   recruitment event.** One evening a week, October–November: rookies drive
   `simulateJava`, climb curriculum rungs, and get time on the real 2026 robot. Teams
   that go quiet from September to January lose their fall recruits ([Chief Delphi:
   subteam recruitment](https://www.chiefdelphi.com/t/subteam-recruitment/503104),
   [recruitment](https://www.chiefdelphi.com/t/recruitment/494997)). The profile notes
   2027Robot activity went quiet for everyone but Stephen after May — this is the
   momentum leak. Cost: 6 × 2 mentor-hours, but rungs are self-serve, so an "on-and-off"
   mentor can run a session from `MENTOR-PLAYBOOK.md` without Stephen present.

3. **Convert occasional mentors into rung-checkers, not co-leads.**
   `docs/team/MENTOR-PLAYBOOK.md` is a 5-minute read that gives a drop-in mentor a
   concrete, bounded job for that visit (sit with a student on their current rung, use
   the checklist, sign off). This turns intermittent attendance from "helped one kid with
   one bug" into "advanced one student one permanent rung," with zero prep. Cost: the
   playbook exists; recurring cost lands on the occasional mentors, not the lead.

---

## Sequencing

```
Now (offseason)      → Review/adopt curriculum + playbook. Student GitHub accounts.
                       Announce fall on-ramp (see RECRUITMENT.md tactics).
October–November     → 6-week on-ramp. Rookies reach rung 4–6. Identify the 1–2
                       students who push past rung 6 unprompted — they're your
                       future near-mentors/captains.
December             → Bus-factor pass: record the Vision.java walkthrough (below),
                       have the strongest student present rung 12 to the team.
Build season (Jan+)  → Rung level = task assignment level. Rung 6+ students own a
                       feature switch each. On-and-off mentors keep running rungs
                       with the long tail.
Post-season          → Each student's commit history under their own name is their
                       season portfolio. Use it for recruiting next fall's pitch.
```

The dependency that matters: **attribution and curriculum must precede the on-ramp**,
because the on-ramp's retention mechanism is "your commit is in the robot repo, under
your name, by week 2."

---

## 1. Recruitment

See `docs/team/RECRUITMENT.md` for the pitch draft and five tactics ranked by effort.
Summary of the strategy: stop selling "join robotics" and sell the three things this
program has that almost no small team has — AI-agent-assisted development, replay-based
debugging of real match logs, and custom internal tooling (logbench) that students can
extend. Target 9th–10th graders specifically; they pay dividends for multiple years
([Chief Delphi: recruiting students](https://www.chiefdelphi.com/t/recruiting-students/129979)).

Mentor cost: front-loaded (one demo prepared once, reused at every event). The
highest-leverage tactic — a live `simulateJava` + logbench demo at the school clubs
fair — costs ~2 hours to prepare the first time and ~0 thereafter.

## 2. Retention (why a joiner stays past week 3)

The profile's power-law contribution curve is a retention diagnosis: students who never
get a real contribution to land, leave. Mechanisms, cheapest first:

- **A commit in week 1–2.** Rung 2 of the curriculum (an `@AutoLogOutput` field) is a
  real, shippable change a student makes in one session and can see live in
  AdvantageScope. Nothing retains like "my code is on the robot."
- **Visible progress ladder.** The curriculum's rung numbers give students a public
  level system. Track rung completion on a whiteboard or a table in the repo — social
  proof and friendly competition for free.
- **Individual attribution.** A student who can point a parent or a college at *their*
  commit history has a reason to keep building it. This also fixes the profile §3 gap
  (shared `Finney Student` account makes individual growth invisible).
- **Peer recruiting loop.** Retained sophomores are next year's best recruiters —
  students respond to peers, not mentors, at clubs fairs
  ([Chief Delphi: how to get freshmen interested](https://www.chiefdelphi.com/t/how-to-get-freshman-interested-in-robotics/355476)).
- **Ice-breakers/snacks/bonding matter more than software mentors want to believe**
  ([Chief Delphi: subteam recruitment](https://www.chiefdelphi.com/t/subteam-recruitment/503104)).
  This is a perfect job for an on-and-off mentor or a parent — it needs presence, not
  codebase context. Put it in the playbook, not on Stephen.

## 3. Bus-factor risk

The risk (profile §4): the vision pipeline, replay boundary, and logbench internals live
in one person's head. Attack in three tiers, cheapest first:

- **Tier 1 — record it once (≈2 mentor-hours).** A 30–45 min screen recording of Stephen
  walking through `Vision.periodic()` — the replay boundary, the filter order, why
  `processInputs()` must come first — plus one recording of "how I debug a match with
  `replayWatch` + logbench." Docs exist (`docs/vision-testing-protocol.md`,
  `docs/replay-workflow.md`) but the profile is right that they're written for someone
  who already thinks in the abstractions; a walkthrough video is the missing bridge, and
  it's front-loaded.
- **Tier 2 — the curriculum is the succession plan.** Rungs 9–12 exist specifically to
  produce a second person who can reason about `Vision.java` and write a logbench spec.
  Getting *one* student to rung 12 per season is the measurable bus-factor goal.
- **Tier 3 — teach-back.** The rung-12 student presents the vision pipeline to the team
  (the repo already has `docs/vision/VisionTalk.md` as a model). Teaching it is the test
  that the knowledge actually transferred, and the presentation doubles as recruitment
  material.

What *not* to do: don't try to document every internal exhaustively. Docs that no second
person reads don't reduce bus factor; a second person who can navigate does.

## 4. Converting on-and-off mentors into leverage

Reframe: stop hoping they become leads; give them a bounded, high-value, zero-prep job.
`MENTOR-PLAYBOOK.md` defines three roles an occasional mentor can pick up in the first
five minutes of a visit:

1. **Rung-checker** — sit with a student on their current curriculum rung, use its
   checklist, sign off, have them commit under their own name.
2. **Session-runner** — run a fall on-ramp evening from the script (open sim, assign
   rungs, order pizza). Needs zero codebase knowledge.
3. **Culture-keeper** — bonding, snacks, celebrating rung completions. Explicitly a real
   job, per the retention evidence above.

The common thread: each role converts an unpredictable visit into a durable increment
(a signed-off rung, a run session, a retained student) instead of ephemeral 1:1 help.

## 5. Things considered and deprioritized

- **A formal classroom-style Java course.** Teams consistently report lecture-style
  training loses students; project-first with just-in-time concepts wins
  ([Chief Delphi: teaching new members programming](https://www.chiefdelphi.com/t/teaching-new-members-programming/458293),
  [how do you teach programming members quickly](https://www.chiefdelphi.com/t/how-do-you-teach-programming-members-quickly/466580)).
  The curriculum embeds concepts in rungs instead.
- **Recruiting new lead mentors externally.** Worth doing opportunistically (alumni,
  parent engineers), but it's slow, low-probability, and not something this plan can
  schedule. The playbook squeezes more from the mentors who already show up.
- **Middle-school/FLL feeder program.** Likely the best *long-term* pipeline builder,
  but it's a permanent recurring mentor obligation — exactly what §7 warns against —
  until there's a second consistent mentor to own it. Revisit if an on-and-off mentor
  wants to own it outright.

---

## Assumptions to verify (open questions from PROFILE.md §6 that shaped this plan)

1. **Fall availability:** assumed students can make one ~2-hour evening/week in
   Oct–Nov, and that the school allows an offseason meeting space. If not, the on-ramp
   compresses to bi-weekly and the retention math weakens.
2. **Team size / software share:** assumed software is ~5–10 students out of a larger
   team, and that recruiting *into software from the existing team* is as viable as
   recruiting new students to the team. If the whole team is tiny, RECRUITMENT.md's
   clubs-fair tactic is the priority; if the team is big but software is small,
   internal recruiting is cheaper.
3. **Hardware access in fall:** assumed the 2026 robot is drivable in the offseason.
   If not, the sim carries the whole on-ramp (it can — that's why rungs 1–8 are
   sim-first), but "drive the real robot" is the best hook and worth fighting for.
4. **GitHub policy:** assumed students can create individual GitHub accounts and be
   added to the repo (school/parental policy permitting). If not, at minimum set
   per-student `git config user.name` on shared machines so commits are attributable.
5. **Recruitment history:** assumed a school clubs fair (or equivalent) exists and
   hasn't yet been worked with a live demo. If prior attempts already did this and
   failed, the peer-led classroom-visit tactic moves up.
6. **Success horizon:** assumed the 1-year definition of success is: 3+ new students
   reaching rung 4+, one student at rung 12, all commits attributed; and the 3-year
   definition is a student-led software subteam where Stephen reviews more than he
   writes. If the mentor's actual priority is competition results first, the bus-factor
   tier ordering shifts (driver practice and reliability beat curriculum polish).
7. **On-and-off mentor identity:** assumed the occasional mentors are adults with some
   technical comfort (can follow a checklist involving an IDE) even if they don't know
   this codebase. If some are non-technical, they map to the session-runner and
   culture-keeper roles only — still valuable.

Sources: [Subteam recruitment](https://www.chiefdelphi.com/t/subteam-recruitment/503104) ·
[Recruitment](https://www.chiefdelphi.com/t/recruitment/494997) ·
[Recruiting students](https://www.chiefdelphi.com/t/recruiting-students/129979) ·
[How to get freshmen interested in robotics](https://www.chiefdelphi.com/t/how-to-get-freshman-interested-in-robotics/355476) ·
[Teaching new members programming](https://www.chiefdelphi.com/t/teaching-new-members-programming/458293) ·
[How do you teach programming members quickly](https://www.chiefdelphi.com/t/how-do-you-teach-programming-members-quickly/466580)
