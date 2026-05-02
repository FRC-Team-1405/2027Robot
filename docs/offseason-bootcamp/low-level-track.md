# Beginner Track

This track is for new students or students who still need repetition on core programming concepts before they can contribute confidently to a larger robot codebase.

## Track Goal

Teach Programming 101 through robot-flavored examples so students can understand the code they are reading and safely make small, correct changes.

## Outcomes

- Understand what a class, object, method, variable, constant, and enum are.
- Read simple Java robot code and explain what each file is responsible for.
- Write small classes and methods with clear names and purpose.
- Use constants instead of magic numbers.
- Follow basic subsystem and command structure.
- Add simple logging and use it to debug behavior.

## Suggested Module Flow

1. Java basics
   - Variables, types, conditionals, loops, methods, return values
   - Classes, constructors, fields, and objects
2. Code organization
   - What belongs in a subsystem, command, constants file, and container
   - Why naming and file structure matter
3. Robot-code basics
   - Scheduler overview
   - Subsystem responsibilities
   - Commands as actions
   - Controller input wiring
4. Safe coding habits
   - Constants instead of hard-coded values
   - Small focused methods
   - Logging and simple dashboard output
   - Reading existing code before editing
5. Debugging basics
   - What to log
   - How to test one change at a time
   - How to tell whether a problem is input, logic, or hardware-facing code
6. Mini robot exercises
   - Add a simple command
   - Add one logged value
   - Write a small subsystem-like class with state and methods

## Beginner Practice Ideas

- Create a small practice class that models a mechanism state.
- Add constants to replace hard-coded values in sample code.
- Write a simple command that calls a subsystem method.
- Log one sensor value and one desired state value.
- Explain the role of `Robot`, `RobotContainer`, a subsystem, and a command in plain language.

## Exit Criteria

A student is ready to move beyond this track when they can:

- Explain the purpose of a class and a method without guessing.
- Read a short Java file and identify fields, methods, constants, and control flow.
- Make a small code change without breaking project structure.
- Follow team naming and constants patterns.
- Add basic logging to confirm a hypothesis while debugging.
- Describe how a command interacts with a subsystem.

## Notes for Mentors

- Keep the examples small and repeatable.
- Use robot examples early so abstract ideas feel relevant.
- Do not assume that a student who can copy code understands the structure behind it.
- Prefer many short exercises over one big assignment.
