# Recruitment — pitch draft + tactics

Draft material for the mentor to edit and deliver. Nothing here has been sent or posted.
The strategy: don't sell "robotics club" — every club at the fair is selling that. Sell
the three things this program has that a small school almost never has: **AI-assisted
software development, replaying real matches like game film, and building your own
tools.**

---

## The pitch (one-pager — for a flyer, a slide, or reading aloud in a classroom visit)

### Write code. Put it on a 120-pound robot. Watch it play.

Most coding classes end with a program that prints text. Ours ends with a swerve-drive
robot doing what you told it to, in front of a crowd, in a competition that does not
wait for you to fix your bugs.

**Here's what's different about software on Team 1405:**

- **You ship in week two.** Our onboarding ladder starts with driving a full physics
  simulation of the robot on your laptop — no robot required, no waiting your turn. By
  your second meeting, a change *you* wrote is in the robot's code, committed under
  *your* name. Your GitHub history becomes a portfolio you can show colleges and
  employers: not "I was in robotics club," but *here is the code I wrote, here's the
  match it ran in.*

- **We replay matches like game film.** Every match the robot plays is recorded — every
  sensor reading, every camera frame's pose estimate. We re-run those recordings
  through new code on a laptop: change a line, replay the match, watch history come
  out differently. When something goes wrong at competition, we don't guess — we
  replay it and find it. Almost no team our size debugs this way.

- **We build our own tools.** The team wrote its own match-playback dashboard
  (a web app — React front end, Python back end), its own camera-calibration app, its
  own analysis pipeline. If you're more interested in web dev or data than robots,
  there's real work here for you too — tools the team actually uses every week.

- **You'll work the way software is actually built now.** Our mentor develops with AI
  coding agents daily, and you'll learn to use them the way professionals do: directing
  them, reviewing what they produce, knowing when they're wrong. That's a skill most
  adults don't have yet.

- **Real hardware, real stakes.** Vision processing on coprocessors, CAN networks,
  brushless motor control, autonomous routines. It's the same stack as real robotics
  companies, scaled to fit in a school build room.

**No experience needed.** If you've written a loop in any language, rung 1 of our
ladder is built for you. Come to one fall session, drive the simulator, and decide.

*[Insert: meeting day/time/room, mentor contact, QR code to sign up]*

---

## Tactics, ranked by effort to run

Ranked cheapest-to-run first. Two channels are mixed in here on purpose: the school
(tried before, per `PROFILE.md` §5a, with weak results) and the homeschool community
(never tried deliberately, and per the mentor's own read of the team, the highest-
confidence channel available — roughly half the team is already homeschoolers, recruited
by word of mouth alone, and they tend to be the strongest contributors). Don't let the
school-side tactics below crowd out #1 and #2 just because they're more familiar.

### 1. Ask current homeschool students/parents to open a door (lowest effort, warmest lead)
The team's own homeschool students and their parents are already connected to
co-ops, enrichment groups, or homeschool social circles that have never been reached
deliberately. Before writing any cold outreach, ask: *"Would you be willing to share
this with your co-op / homeschool group, or introduce us to whoever runs it?"* A warm
introduction from a family already in those circles will outperform a cold email from
the team, and it costs one conversation. Pair it with the one-pager below.

### 2. Direct outreach to 1-2 homeschool co-ops or groups (low effort, high confidence)
Draft an email (or a message to a homeschool Facebook/Discord group, whichever the local
groups actually use) built from the one-pager below, and send it to one or two homeschool
co-ops, enrichment programs, or support groups. The mentor doesn't need to know exactly
which groups yet — that's local knowledge current homeschool families or a quick search
of local homeschool co-op directories will surface. Draft template:

> Subject: FRC robotics team looking for homeschool students (all experience levels)
>
> Hi [group name] — I help run Team 1405, a competitive FRC robotics team based at
> Charles Finney School in [city]. We build a competition robot every year, and
> homeschool students are already a big part of our team — [N] of them are some of our
> strongest members. We'd love to reach more homeschool students who might be
> interested, especially in software (no experience required — see attached one-pager).
> Happy to answer questions, host a visit, or send more info to interested families.

Cost: ~1 hour to draft, adapt per group, and send. Recurring cost: ~0 (repeat once a
year, or whenever a new group is identified via #1).

### 3. The live sim demo (school clubs fair; low effort after one-time setup)
Laptop at the clubs fair table running `./gradlew simulateJava` with a gamepad, and
AdvantageScope's field view on a second screen. Let students *drive*. Second laptop (or
tab): logbench playing back a real match. The line is "this is our robot in software —
want to see the code that's making it move?" **Setup cost: ~2 hours once** (a
`docs/team/demo-checklist` note with the exact windows to open); per-event cost: carrying
two laptops. Peer-staffed: students run the table, mentors stay home — students respond
to peers, not adults ([Chief Delphi: how to get freshmen interested](https://www.chiefdelphi.com/t/how-to-get-freshman-interested-in-robotics/355476)).

### 4. Sophomore testimonial + flyer in intro CS / math classes (low effort, school-side)
A returning student takes 5 minutes of an intro programming class: shows their own
commit history and one 30-second replay clip, hands out the one-pager above. Target
9th–10th graders deliberately — they compound for three more years
([Chief Delphi: recruiting students](https://www.chiefdelphi.com/t/recruiting-students/129979)).
Cost: one email to the CS/math teacher + printing. Note: school-side channels like this
haven't performed well historically (`PROFILE.md` §5a) — worth doing because it's cheap,
not because it's expected to be the main driver.

### 5. "Fall on-ramp" open sessions (medium effort, doubles as retention)
Advertise the 6-week fall on-ramp (see `GROWTH-PLAN.md`) as a no-commitment "learn to
program a robot" mini-course, not a club membership decision. Lower ask → more walk-ins;
the curriculum ladder converts walk-ins into members by giving them a shipped commit
before they've decided whether to stay. Teams that go dark in the fall lose exactly
these students ([Chief Delphi: subteam recruitment](https://www.chiefdelphi.com/t/subteam-recruitment/503104)).

### 6. Drive the real robot at an event (medium-high effort, big splash)
Run the 2026 robot at a home game halftime, pep rally, or open house — driver station
staffed by students, flyer handout ready. Consider a homeschool-audience version too
(many homeschool co-ops run their own open houses/showcases) — same setup, different
room. Highest per-event impressions; costs robot transport, safety perimeter, and 2–3
mentor-hours. Do it once per fall, timed a week before the on-ramp starts so there's an
immediate next step to funnel into.

### 7. Parent/teacher/co-op newsletter channel (low effort, slow burn)
One paragraph in the school newsletter and an email teachers can forward, built from the
one-pager — and the same paragraph to any homeschool co-op newsletter or list-serv
reachable via tactic #1 or #2. Mention the college-portfolio angle explicitly — that's
the line parents respond to, and homeschool parents in particular tend to value a
structured, portfolio-building extracurricular. Cost: 30 minutes once a year. Don't
expect volume from the school version; do expect the occasional exactly-right student
whose parent saw it.

---

*Sources: [Recruiting students](https://www.chiefdelphi.com/t/recruiting-students/129979) ·
[Subteam recruitment](https://www.chiefdelphi.com/t/subteam-recruitment/503104) ·
[How to get freshmen interested in robotics](https://www.chiefdelphi.com/t/how-to-get-freshman-interested-in-robotics/355476) ·
[Recruitment](https://www.chiefdelphi.com/t/recruitment/494997)*
