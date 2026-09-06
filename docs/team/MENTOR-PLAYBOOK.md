# Mentor Playbook — for the mentor who shows up sometimes

You showed up tonight. That's the hard part, and it's enough — this page turns tonight's
visit into something permanent without asking you to become a lead, learn the codebase,
or come back on any schedule.

**Read time: 5 minutes. Prep required: none.**

## The one idea

Unstructured 1:1 help evaporates when you leave. A **signed-off curriculum rung** does
not: it's a commit in the repo, under the student's name, forever. So instead of "help
whoever looks stuck with whatever they're stuck on," pick one of these three jobs for
the visit. All three are real contributions to team-building; none requires knowing how
the robot code works.

---

## Job 1: Rung-checker (if you're comfortable sitting at an IDE)

1. Ask any student: **"What rung are you on?"** (Everyone has an answer; it's on the
   roster at the bottom of `docs/team/onboarding/CURRICULUM.md`, and rungs 1–8 need no
   robot and no codebase expertise from you.)
2. Sit with them while they work it. Your job is not to know the answer — it's to ask
   the questions in the rung's **"Done when"** checklist and refuse to be hand-waved.
   "Show me." "Run it." "What did you predict would happen?"
3. When the checklist passes, they commit with the rung tag (`rung-3: ...`) from the
   shared student account, but **the commit message must include a `Student: <Name>`
   line** — check that it's there, that's what makes it count as theirs. (Individual
   GitHub accounts were considered and deliberately skipped — the setup/laptop-swap
   friction wasn't worth it. This trailer gets the same effect for free.)
4. Update their row in the roster table at the bottom of CURRICULUM.md.

You just advanced a student one permanent level in one visit. If you only ever do this
job, you are pulling real weight.

**If a student is stuck beyond your depth:** don't burn the visit spinning. Have them
write the question in the team chat / an issue for the lead mentor with what they tried,
then drop back one rung and solidify it tonight instead. Unblocking asynchronously is
the lead's job; keeping momentum is yours.

## Job 2: Session-runner (no technical comfort needed)

Fall on-ramp nights and meetings run on a script, not on expertise:

1. Unlock the room, get laptops open, get `./gradlew simulateJava` running on each
   (rung 1 of the curriculum is literally the instructions — students who've done it
   help the ones who haven't; let them).
2. Ask each student their rung, point them at it, keep the room on-task.
3. Food. Genuinely. Snacks and a hard stop time are retention infrastructure.
4. End with a 2-minute round: everyone says what rung they hit. Applaud completions.

## Job 3: Culture-keeper (no laptop needed)

The evidence from other teams is blunt: bonding, snacks, and someone learning students'
names retain members as much as curriculum does. If tech isn't your lane: run the
ice-breaker, learn who's new, notice who's drifting toward the door by week 3 and talk
to them, celebrate rung-12 presentations like they're wins at competition — they are.

---

## Things that help, whichever job you pick

- **Never take the keyboard.** Point at the screen, ask questions, make them type it.
  The rung isn't done if you did it.
- **"I don't know, let's find out" is a great answer.** Modeling how to read an error
  message or search the docs is more valuable than knowing the answer.
- **Struggle is fine; drowning is not.** Ten minutes of productive struggle builds a
  programmer. Forty minutes of silent drowning loses a team member. Check in.
- **Log what happened.** One line in the team chat when you leave: who you worked with,
  what rung, signed off or not. That's how the lead mentor plans around visits nobody
  could schedule.

## What NOT to worry about

- You don't need to understand AdvantageKit, the vision pipeline, or swerve drive.
  Rungs 9+ students mostly need an *audience*, not an expert — "explain it to me like
  I'm new" is you doing your job, and their teach-back is the point (see rung 12).
- You don't need to commit to next week. Three visits a season, run this way, beats
  weekly attendance spent hovering.
- You can't really break anything. Students work on branches; the build catches most
  mistakes; nothing deploys to a robot unless a lead does it.
