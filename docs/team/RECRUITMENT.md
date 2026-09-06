# Recruitment — pitch draft + tactics

Draft material for the mentor to edit and deliver. Nothing here has been sent or posted.
The strategy: don't sell "robotics club" — every club at the fair is selling that. Sell
the three things this program has that a small school almost never has: **AI-assisted
software development, replaying real matches like game film, and building your own
tools.**

---

## The pitch (one-pager — student-facing flyer or classroom handout)

### Build something real. Find your place on the team.

**You do not need to know how to code, build a robot, or even know exactly what you are
interested in yet.** Team 1405 is a place to learn by working alongside other students on
a real challenge: designing, building, programming, and competing with a new robot each
year.

This is not a class where everyone follows the same instructions and ends with the same
project. The robot gives us problems no one has solved for us. Students share ideas, test
them, learn from what fails, and make the next version better. Your first contribution may
be small, but it will be part of something the whole team depends on.

**There is meaningful work here for many kinds of people.** You might design a mechanism,
wire electronics, program autonomous movement, analyze match data, create a scouting or
web tool, make media, develop strategy, or help organize the team. You do not have to
arrive knowing which role fits you. Trying things and discovering what you enjoy is part of
the experience.

If you choose software, you can begin in a full robot simulator before touching the real
machine. As your skills grow, you can work with sensors and cameras, control motors, build
autonomous routines, or improve tools the team uses. We record matches and replay them like
game film, allowing students to investigate what happened and test how a code change would
perform. Students also learn how modern developers use AI tools responsibly: not as a
substitute for thinking, but as something to direct, question, test, and improve.

**What you build here also builds you.** Robotics gives you practice asking questions,
explaining your ideas, working through frustration, and trusting teammates with real
responsibility. You can become more confident without being expected to be outgoing on day
one. Over time, you will have genuine projects and competition experiences to discuss in
college applications, interviews, and future work—not simply a club name on a list.

**Come to one meeting and see what it is actually like.** Meet the team, explore the robot,
and try the simulator. There is no pressure to arrive prepared or to commit before you know
whether it is right for you.

*[Insert: grades/ages served, meeting day/time/location, season dates, cost if any, mentor
contact, and QR code to visit or sign up]*

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
the team, and it costs one conversation. Pair it with the student-facing one-pager above.

### 2. Direct outreach to 1-2 homeschool co-ops or groups (low effort, high confidence)
Send an email (or a message to a homeschool Facebook/Discord group, whichever the local
groups actually use) to one or two homeschool co-ops, enrichment programs, or support
groups. The mentor doesn't need to know exactly which groups yet — that's local knowledge
current homeschool families or a quick search of local homeschool co-op directories will
surface.

#### Co-op email — Draft 1 (original)

> Subject: FRC robotics team looking for homeschool students (all experience levels)
>
> Hi [group name] — I help run Team 1405, a competitive FRC robotics team based at
> Charles Finney School in [city]. We build a competition robot every year, and
> homeschool students are already a big part of our team — [N] of them are some of our
> strongest members. We'd love to reach more homeschool students who might be
> interested, especially in software (no experience required — see attached one-pager).
> Happy to answer questions, host a visit, or send more info to interested families.

#### Co-op email — Draft 2 (for homeschool parents)

> Subject: A place for homeschool students to build STEM skills—and confidence
>
> Hi [name/group],
>
> Finding the right group experience for a homeschooled teenager can be difficult. Many
> parents are looking for more than another class: they want a place where their student
> can make friends around a shared interest, become more comfortable working with others,
> and discover that STEM can be creative, practical, and genuinely exciting.
>
> Team 1405, the Charles Finney Falcons, is a competitive FIRST Robotics Competition team
> in [city], and we welcome homeschool students [in grades/ages]. Each year, students and
> mentors work together to design, build, program, and compete with a full-size robot.
> Homeschool students are already an important part of our team, so a new student would
> not be the only one joining from outside a traditional school classroom.
>
> **No previous robotics, engineering, or programming experience is required.** Students
> learn alongside teammates and adult mentors through real projects, with room to explore
> mechanical design, electronics, software, strategy, data, media, and team organization.
> This can provide the hands-on STEM instruction and inspiration that are often difficult
> to recreate at home—without asking a parent to become the robotics teacher.
>
> **The benefits go beyond STEM.** Because every student contributes to a shared goal,
> they have a natural reason to talk, collaborate, solve disagreements, ask for help, and
> take responsibility. Quieter or less-confident students can begin with a manageable task
> and build toward presenting an idea, leading a project, or representing the team at a
> competition. Friendships grow out of doing meaningful work together rather than being
> forced through a purely social activity.
>
> **Your student can visit before deciding.** We would be glad to host interested families
> at a meeting, show them the robot, and let students [try the simulator/participate in a
> simple hands-on activity]. Our next opportunity is [date/time/location]. Families can
> learn more or sign up here: [link].
>
> Would you be willing to share this invitation with families in [co-op/group name]? I am
> also happy to answer questions about scheduling, cost, supervision, or what a first-year
> student can expect.
>
> Thank you,
>
> [name]<br>
> [role], FRC Team 1405 — Charles Finney Falcons<br>
> [email/phone] | [website]

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
A returning student takes 5 minutes of an intro programming class: shows one project they
helped build and one 30-second replay clip, then hands out the one-pager above. Target
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
