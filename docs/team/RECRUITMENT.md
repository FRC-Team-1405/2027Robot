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

Ranked cheapest-to-run first. Assumption (flagged in `GROWTH-PLAN.md`): the school has
a clubs fair or equivalent, and classroom visits are possible.

### 1. The live sim demo (lowest effort after one-time setup; highest hook rate)
Laptop at the clubs fair table running `./gradlew simulateJava` with a gamepad, and
AdvantageScope's field view on a second screen. Let students *drive*. Second laptop (or
tab): logbench playing back a real match. The line is "this is our robot in software —
want to see the code that's making it move?" **Setup cost: ~2 hours once** (a
`docs/team/demo-checklist` note with the exact windows to open); per-event cost: carrying
two laptops. Peer-staffed: students run the table, mentors stay home — students respond
to peers, not adults ([Chief Delphi: how to get freshmen interested](https://www.chiefdelphi.com/t/how-to-get-freshman-interested-in-robotics/355476)).

### 2. Sophomore testimonial + flyer in intro CS / math classes (low effort)
A returning student takes 5 minutes of an intro programming class: shows their own
commit history and one 30-second replay clip, hands out the one-pager above. Target
9th–10th graders deliberately — they compound for three more years
([Chief Delphi: recruiting students](https://www.chiefdelphi.com/t/recruiting-students/129979)).
Cost: one email to the CS/math teacher + printing.

### 3. "Fall on-ramp" open sessions (medium effort, doubles as retention)
Advertise the 6-week fall on-ramp (see `GROWTH-PLAN.md`) as a no-commitment "learn to
program a robot" mini-course, not a club membership decision. Lower ask → more walk-ins;
the curriculum ladder converts walk-ins into members by giving them a shipped commit
before they've decided whether to stay. Teams that go dark in the fall lose exactly
these students ([Chief Delphi: subteam recruitment](https://www.chiefdelphi.com/t/subteam-recruitment/503104)).

### 4. Drive the real robot at a school event (medium-high effort, big splash)
Run the 2026 robot at a home game halftime, pep rally, or open house — driver station
staffed by students, flyer handout ready. Highest per-event impressions; costs robot
transport, safety perimeter, and 2–3 mentor-hours. Do it once per fall, timed a week
before the on-ramp starts so there's an immediate next step to funnel into.

### 5. Parent/teacher channel (low effort, slow burn)
One paragraph in the school newsletter and an email teachers can forward, built from
the one-pager. Mention the college-portfolio angle explicitly — that's the line parents
respond to. Cost: 30 minutes once a year. Don't expect volume; expect the occasional
exactly-right student whose parent saw it.

---

*Sources: [Recruiting students](https://www.chiefdelphi.com/t/recruiting-students/129979) ·
[Subteam recruitment](https://www.chiefdelphi.com/t/subteam-recruitment/503104) ·
[How to get freshmen interested in robotics](https://www.chiefdelphi.com/t/how-to-get-freshman-interested-in-robotics/355476) ·
[Recruitment](https://www.chiefdelphi.com/t/recruitment/494997)*
