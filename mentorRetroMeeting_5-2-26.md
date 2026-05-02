# Mentor Retro Meeting To-Do List

## External Outreach

- Reach out to the Symbiotics Robotics Team and schedule a virtual meeting to discuss software.
- Review Symbiotics' published codebase before the meeting, especially drive base behavior, power draw, battery management, and any software-side current limiting or predictive modeling.
- Prepare a list of questions for Symbiotics about high current draw, battery usage across a match, and any logging or telemetry practices they use.
- Reach out to people in the company to see who is interested in helping with offseason programming meetings for students.

## Purchases and Resources

- Order a CANCoder for testing and offseason development.
- Buy a Phoenix Tuner Pro subscription for configuration, logging, and testing.
- Take inventory of available hardware, including cameras, Orange Pi units, other coprocessors, spare motor controllers, sensors, and anything else useful for offseason projects or training.

## Technical Analysis

- Analyze Symbiotics' drive code and note any useful ideas related to current draw, battery usage, current limiting, predictive modeling, logging, and telemetry.
- Review competition and match logs to identify current spikes, brownouts, battery sag, and any correlation with drive maneuvers.
- Review current vision pipeline work, including coprocessor vs. RIO computation, multi-tag vs. single-tag accuracy, and different camera configurations.
- Profile Orange Pi CPU and GPU usage under different camera counts to understand current limits and future feasibility.

## Student Programming Boot Camp

- Define the boot camp goal: first build programming fundamentals and robot-specific habits, then transition into actual offseason projects later in the fall.
- Create a rough outline for the overall boot camp so there is a clear progression from basic programming concepts to robot-specific implementation work.
- Create a beginner track for brand new students that covers Programming 101 topics such as classes, methods, variables, control flow, object-oriented basics, and how those ideas map to robot code.
- Create an advanced track for returning or more experienced students that focuses on reprogramming the existing robot from scratch or programming a new robot from scratch.
- Decide how students will be placed into the beginner or advanced track based on experience, comfort level, and demonstrated fundamentals. *(Added)*
- Define the core robot-specific modules students should work through, including subsystem structure, command-based patterns if applicable, logging, testing, debugging, sensors, and best practices.
- Identify the most important basic concepts current software students are still missing and make sure those are explicitly covered early in the boot camp.
- Separate boot camp curriculum from offseason project work so training does not get mixed together with project execution.

## Offseason Project Planning

- Draft the offseason project list with goals, requirements, and expected outcomes for each item.
- Include battery draw analysis as a possible offseason project.
- Include data sharing and export tools as a possible offseason project.
- Include a drive base with multi-side cameras as a possible offseason project.
- Include vision odometry accuracy improvements as a possible offseason project.
- Include Orange Pi CPU and GPU usage analysis as a possible offseason project.
- Leave room for student-led project ideas and ownership opportunities.
- Prepare a structured student sign-up and idea collection process for offseason projects, including project selection, student-proposed ideas, and expected deliverables.
- Define when boot camp ends and when project work begins so the offseason timeline is easier to communicate. *(Added)*

## Documentation and Best Practices

- Update the team's best practices documents.
- Expand the best practices documents to better cover logging expectations and any additional ideas learned during competition.
- Review whether the best practices documents should also include clearer guidance for subsystem design, naming, code organization, and debugging workflow. *(Added)*
- Create simple reference material or examples that students can reuse during training, such as example subsystem structure, example logging patterns, and example class/method organization. *(Added)*

## Meeting Preparation

- Prepare materials for the retrospective software meeting.
- Bring the offseason project list, findings from the Symbiotics discussion, hardware inventory results, and battery analysis insights.
- Prepare a rough teaching plan for the offseason meetings so the mentor group can react to the proposed beginner and advanced tracks.
- Identify what mentor help, staffing, and time commitment will be needed to run two separate student tracks well. *(Added)*

## Notes

- Items marked with *(Added)* were suggestions added during the rewrite to make the to-do list more complete and easier to execute.
- The boot camp work is separate from the actual offseason project work and should come first, with project execution starting later once students have a stronger foundation.

## Related Documentation

- Boot camp overview: `docs/offseason-bootcamp/README.md`
- Beginner track: `docs/offseason-bootcamp/low-level-track.md`
- Advanced track: `docs/offseason-bootcamp/advanced-track.md`
- Offseason project summary: `docs/offseason-bootcamp/offseason-projects-summary.md`
- Individual project guides: `docs/offseason-bootcamp/projects/`
