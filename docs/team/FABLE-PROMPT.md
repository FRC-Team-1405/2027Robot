# Prompt fed to Fable (2026-09-06)

Kept for the record — this is the instruction handed to the Fable-5 agent run tasked with
turning `docs/team/PROFILE.md` into a concrete growth plan for FRC Team 1405.

---

You're working for the software mentor of FRC Team 1405 (Charles Finney Falcons, a small
high-school robotics team in New York). Read `docs/team/PROFILE.md` first — it's a grounded
profile of the team's mentor capacity, student pipeline, technical program, and stated goals,
built from git history and the mentor's own description. Treat it as ground truth; don't
re-derive it.

The team wants to grow: attract more students to the software sub-team, and build a program
that's less dependent on one or two people (the mentor is currently ~44% of all commits some
seasons; students mostly touch the code a handful of times each, via a shared, non-attributed
account). Section 6 of the profile lists open questions you can't answer from the repo (team
size, school support, recruitment history, competition record, mentor pipeline, time horizon).
Don't block on these — state the assumption you're making wherever one of them would change
your recommendation, so the mentor can correct you in one pass instead of you guessing silently.

Section 7's constraints are load-bearing: prefer solutions that are built once and reused over
solutions that need recurring mentor attention, prefer a incremental skill ladder over
expecting a jump straight to the existing architecture's abstraction level, and be honest that
mentor time is the scarcest resource — a plan that costs mentor hours once to save mentor hours
every year after is good; a plan that adds a permanent weekly obligation is suspect.

## What to produce

Everything goes under `docs/team/`. Do not touch `src/`, `tools/`, or anything outside
`docs/team/` — this is a planning exercise, not a code change. Do not run `git commit` or
`git push`; leave the files for the mentor to review as a diff. Do not take any action outside
this filesystem (no emails, no web posts, no purchases) — web research/citations are fine and
encouraged (this team already cites ChiefDelphi threads in its own docs; match that standard),
but everything you produce is a draft for a human to send, not something you send yourself.

1. **`docs/team/GROWTH-PLAN.md`** — a prioritized plan, not a brainstorm dump. Organize by
   what it actually costs the mentor vs. what it buys the team, and be explicit about
   sequencing (what should happen before what). Cover at minimum: recruitment, retention
   (why would a student who joins stay past week 3), reducing bus-factor risk, and converting
   "on-and-off" mentors into more leveraged (even if still occasional) contributors. Flag your
   top 3 recommendations clearly — this document will be skimmed before it's read in full.

2. **`docs/team/onboarding/CURRICULUM.md`** — a rung-by-rung ladder of first real
   contributions a first-year student with "basic programming" ability (per the profile) could
   make to *this specific codebase*, ordered from trivial to "now they can read Vision.java."
   Ground every rung in an actual pattern/file from this repo or `2026Robot` (e.g., adding an
   `@AutoLogOutput` field, writing a small `FooIOSim` tweak, adding a `FeatureSwitches` flag and
   wiring it to one `if`, extending a `logbench` spec) — read the code, don't invent generic
   programming exercises unrelated to what this team actually builds. Each rung should name
   the concept it teaches and roughly how long it should take.

3. **`docs/team/RECRUITMENT.md`** — a draft pitch (one-pager length) aimed at a student who
   hasn't joined yet, and separately, 3-5 concrete recruitment tactics ranked by
   effort-to-run. Use what's actually distinctive about this program as the hook (AI-agent-
   assisted development, custom internal tooling like logbench, replay-based debugging,
   real hardware) rather than generic "join robotics" copy.

4. **`docs/team/MENTOR-PLAYBOOK.md`** — short, concrete guidance for turning a mentor who
   shows up occasionally for 1:1 help into someone more useful to team-building, without
   requiring them to suddenly become a lead. Assume they have little context loaded — the
   playbook should be something an occasional mentor can read in 5 minutes and act on the
   same visit.

Where you had to guess at an open question from Section 6 to write any of the above, collect
those assumptions in a short closing section of `GROWTH-PLAN.md` titled "Assumptions to
verify" so they're all in one place.

Report back a short summary of what you wrote and the single highest-leverage thing you'd
do first if the mentor only had time for one.
