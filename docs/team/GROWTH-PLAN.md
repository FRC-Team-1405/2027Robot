# Growth Plan — FRC 1405 Software Program

Built from `docs/team/PROFILE.md` (treat that as ground truth for capacity/pipeline claims).
Organizing principle, per the profile's §7 constraints: **mentor hours are the budget.**
Every item below is priced in mentor time, and anything recurring had to justify itself.

Drafted 2026-09-06. Everything here is a draft for the mentor to edit and act on — nothing
has been sent, posted, or committed on your behalf.

---

## Top 3 recommendations (if you skim nothing else)

1. **Adopt the onboarding ladder now, before kickoff, with attribution that fits how this
   team actually works.** `docs/team/onboarding/CURRICULUM.md` is a 12-rung sequence of
   real contributions to this codebase. Students stay on the shared `Student` account —
   individual GitHub accounts were considered and deliberately rejected (see
   `PROFILE.md` §3): on shared school laptops with low general tech fluency, per-student
   account + git + VS Code setup, redone every laptop swap, is a real tax not worth
   paying. Instead, every rung commit carries a `Student: <Name>` trailer in the message
   body — the "my work is in the permanent record under my name" effect survives without
   any account plumbing. The roster table at the bottom of `CURRICULUM.md` is the
   human-readable version of the same thing. It's self-serve by design: a student can run
   rungs 1–5 with no mentor in the room. Cost: ~2 hours of mentor review of the
   curriculum. Recurring cost: ~0.

2. **Send the homeschool outreach email(s) this month.** Per the mentor's own read of the
   team: roughly half the team is already homeschoolers, they tend to be the strongest
   contributors, this channel has never been worked deliberately (no feeder pipeline, no
   structured homeschool outreach — `PROFILE.md` §5a), and the school itself won't invest
   in recruiting for you. This is the single cheapest, highest-confidence lever available
   — cheaper than the live-demo tactic below, because it's one email, not an event. See
   `RECRUITMENT.md`'s tactic #1. Cost: ~1 hour to draft and send. Recurring cost: ~0
   (repeat once a year).

3. **Run a fall on-ramp using the simulator and last year's robot, and make it the
   recruitment event for both channels above.** One evening a week, October–November
   (this fits inside the "school provides space, nothing else" reality — no funding
   needed): rookies drive `simulateJava`, climb curriculum rungs, and get time on the
   real 2026 robot. Teams that go quiet from September to January lose their fall
   recruits ([Chief Delphi: subteam recruitment](https://www.chiefdelphi.com/t/subteam-recruitment/503104),
   [recruitment](https://www.chiefdelphi.com/t/recruitment/494997)). The profile notes
   2027Robot activity went quiet for everyone but Stephen after May — this is the
   momentum leak. Cost: 6-8 × 2 mentor-hours, but rungs are self-serve, so an
   "on-and-off" mentor can run a session from `MENTOR-PLAYBOOK.md` without Stephen
   present.

Converting occasional mentors into rung-checkers (§4) and pulling the RIT thread (§4a)
are both still real, still cheap — they just didn't make the top 3 because they compound
*after* the ladder and the recruitment channel exist, not before.

---

## Sequencing

```
Now (offseason)      → Review/adopt curriculum + playbook. Send the homeschool
                       outreach email(s) (RECRUITMENT.md #1). Have one conversation
                       with the RIT-connected mentor about pulling in RIT students
                       (§4a) — costs an hour, not a program.
October–November     → Fall on-ramp (6-8 weeks). Rookies reach rung 4–6 — that's
                       the realistic ceiling given software students typically show
                       up 1-2 days/week (`PROFILE.md` time budget), so most of the
                       calendar runway for rungs 1-6 should come from here, not from
                       the 6-10 week build season itself. Identify the 1–2 students
                       who push past rung 6 unprompted — they're your future
                       near-mentors/captains.
December             → Bus-factor pass: record the Vision.java walkthrough (below),
                       have the strongest student present rung 12 to the team.
Build season (Jan+)  → Rung level = task assignment level. Rung 6+ students own a
                       feature switch each. On-and-off mentors keep running rungs
                       with the long tail.
Post-season          → Each student's `Student: <Name>` commit trail plus their
                       roster row is their season portfolio. Use it for recruiting
                       next fall's pitch, and for the next homeschool outreach round.
```

The dependency that matters: **attribution and curriculum must precede the on-ramp**,
because the on-ramp's retention mechanism is "your name is on a real commit in the robot
repo by week 2" — that still works with the shared account + commit trailer approach,
it just doesn't require solving account setup first.

---

## 1. Recruitment

See `docs/team/RECRUITMENT.md` for the pitch draft and tactics ranked by effort. Two
channels, and they're not equally proven:

- **Homeschool outreach — untried, high-confidence, cheapest.** Per `PROFILE.md` §1a/§5a:
  roughly half the team is already homeschoolers, they tend to be the strongest
  contributors, and nothing structured has ever been sent to homeschool co-ops/groups —
  today's homeschool students arrived by word of mouth alone. The mentor's own assessment
  is that "an email or two... would get a ton of kids interested." This is now
  `RECRUITMENT.md`'s #1 tactic, ahead of anything school-side.
- **School-side channels — tried, weak, still worth the low-effort ones.** In-school
  announcements and small event demos haven't worked well (§5a). Don't abandon the school
  entirely (it's still the venue, and word-of-mouth there is real), but don't expect the
  clubs-fair-style tactics to carry the plan; they're priced as low-effort/low-certainty
  below, not as the lead strategy.

Shared pitch content for both channels: stop selling "join robotics" and sell the three
things this program has that almost no small team has — AI-agent-assisted development,
replay-based debugging of real match logs, and custom internal tooling (logbench) that
students can extend. Target 9th–10th graders specifically; they pay dividends for
multiple years ([Chief Delphi: recruiting students](https://www.chiefdelphi.com/t/recruiting-students/129979)).

Mentor cost: front-loaded (one pitch written once, reused for the email and every event).

## 2. Retention (why a joiner stays past week 3)

The profile's power-law contribution curve is a retention diagnosis: students who never
get a real contribution to land, leave. Mechanisms, cheapest first:

- **A commit in week 1–2.** Rung 2 of the curriculum (an `@AutoLogOutput` field) is a
  real, shippable change a student makes in one session and can see live in
  AdvantageScope. Nothing retains like "my code is on the robot."
- **Visible progress ladder.** The curriculum's rung numbers give students a public
  level system. Track rung completion on a whiteboard or a table in the repo — social
  proof and friendly competition for free.
- **Attribution without new accounts.** The `Student: <Name>` commit trailer (§ top-3
  item 1) plus the curriculum roster table gives a student something to point a parent or
  a college at — "here's my season" — without the shared-laptop account friction that
  made per-student GitHub accounts a non-starter (`PROFILE.md` §3).
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

## 4a. Mentor pipeline: pull the RIT thread

Per `PROFILE.md` §2a, there's no formal mentor recruitment process — mentors arrive
because a student's parent happens to work in software or similar. That's fine as a
baseline, but there's one specific, already-existing bridge that isn't being used
deliberately: one of the team's lead mentors is senior in RIT's entrepreneurship program
(startup investing + mentoring background).

This is not "go recruit mentors" (correctly deprioritized below as slow and
unschedulable) — it's one conversation with someone already on the team: ask them
whether RIT has students (CS/engineering, or their own entrepreneurship-program network)
who'd want occasional FRC exposure, or whether RIT itself runs a volunteering/outreach
program this could plug into. Cost: one conversation. If it produces even one RIT
student willing to show up a few hours a month, that's a near-mentor who can run
rung-checker sessions (§4) without the multi-year runway a high schooler needs to get
there (§2a's autonomous-lead student is still growing into that role).

## 5. Things considered and deprioritized

- **A formal classroom-style Java course.** Teams consistently report lecture-style
  training loses students; project-first with just-in-time concepts wins
  ([Chief Delphi: teaching new members programming](https://www.chiefdelphi.com/t/teaching-new-members-programming/458293),
  [how do you teach programming members quickly](https://www.chiefdelphi.com/t/how-do-you-teach-programming-members-quickly/466580)).
  The curriculum embeds concepts in rungs instead.
- **Recruiting new lead mentors externally, in general.** Worth doing opportunistically
  (alumni, parent engineers), but as a general strategy it's slow and low-probability —
  not something this plan can schedule. The one exception is the RIT thread (§4a), which
  is specific and cheap enough to pull now rather than defer.
- **Middle-school/FLL feeder program.** Confirmed not to exist (`PROFILE.md` §6) and
  likely the best *long-term* pipeline builder if it did — but it's a permanent
  recurring mentor obligation, exactly what §7 warns against, until there's a second
  consistent mentor to own it. Revisit if an on-and-off mentor (or an RIT near-mentor,
  §4a) wants to own it outright.

---

## Resolved via Q&A (2026-09-06) — no longer assumptions

A first draft of this plan carried several unverified assumptions; a Q&A pass with the
mentor resolved almost all of them, now reflected directly in `PROFILE.md` and above:
team size (~10 mentors/20 students), recruitment history (school channels tried and
weak; homeschool never tried), mentor pipeline (informal, plus the RIT thread), the
near-mentor candidate (an autonomous-lead student, growing), school support (space only),
time budget (6-10 week build season, students typically 1-2 days/week, ~8-10 hrs/week if
committed, no at-home work yet), success priorities (more students *and* deeper technical
ability is the top priority, ahead of competition results, which is treated as
downstream), and the shared-account decision (§ top-3 item 1). No feeder pipeline exists.

## Still genuinely open

1. **Competition results/technical weaknesses.** Deliberately not chased in this plan —
   the mentor's stated priority order (`PROFILE.md` §5) treats competition results as
   downstream of student depth, not a separate lever. Revisit only if a specific failure
   mode (reliability, autonomous consistency) is costing matches independent of this plan.
2. **Whether the homeschool email actually converts.** This is the plan's single
   biggest untested bet (top-3 item 2) — high-confidence per the mentor's own read, but
   unproven. Worth treating the first round as a fast, cheap experiment: send it, see
   what shows up to the fall on-ramp, and adjust before investing more in that channel.
3. **At-home engagement.** The mentor wants students doing work outside meetings, which
   isn't happening today. This plan leans on rung 1 being fully home-portable (no lab,
   no robot, just the sim) as a low-friction first nudge, but hasn't been tested as a
   deliberate retention/engagement lever beyond that.

Sources: [Subteam recruitment](https://www.chiefdelphi.com/t/subteam-recruitment/503104) ·
[Recruitment](https://www.chiefdelphi.com/t/recruitment/494997) ·
[Recruiting students](https://www.chiefdelphi.com/t/recruiting-students/129979) ·
[How to get freshmen interested in robotics](https://www.chiefdelphi.com/t/how-to-get-freshman-interested-in-robotics/355476) ·
[Teaching new members programming](https://www.chiefdelphi.com/t/teaching-new-members-programming/458293) ·
[How do you teach programming members quickly](https://www.chiefdelphi.com/t/how-do-you-teach-programming-members-quickly/466580)
