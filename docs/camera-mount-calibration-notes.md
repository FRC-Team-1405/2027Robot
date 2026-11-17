# Camera mount calibration: what we tried, what we want, what is still open

Started 2026-11-14. This is the running log for one problem: **knowing where each camera is on the
robot, and being able to measure how accurate that knowledge is.** It is deliberately open: we parked
it on 2026-11-14 to come back to. The tool-specific details are in
[camera-autocal-plan.md](camera-autocal-plan.md).

## In short

- **Where we stand:** the camera constants in `VisionConstants.java` match a tape measure and an aim
  check to about 0.2 in and 0.3 deg (yaw ~1.4 deg). **We are keeping them.**
- **What failed:** the automatic "spin & drive" calibration gave a different answer (about 5 in too low,
  3 deg too much pitch, yaw off by 4-9 deg), and the tape says it is the tool that is wrong, because the
  vision it relies on has a few cm of position-dependent error with the small tag pair we used.
- **What we still do not have:** a way to *measure* how accurate a mount is. The missing piece is a
  trustworthy reference for the robot's own centreline and heading, so every other measurement has
  something solid to be compared with.

## What we want

1. **A quick calibration** (minutes, few measurements, little to explain) that gives each camera's
   position and angles relative to the robot origin.
2. **A measured accuracy**, not a hope: a number we can state ("x, y within 5 mm, angles within
   0.3 deg") backed by an independent check against tape.
3. **Both cameras agree at a standstill**, because comparing camera settings on odometry (the
   [crossover experiment](experiments/vision/2026-11-14-pv-crossover-odometry/README.md)) is only as
   good as the mounts.
4. **No extra hardware that lives on the robot**, e.g. a third camera only to say where the robot is.
5. Keep the manual (tape) method alongside any automatic one: it is the reference.

## What we tried (2026-11-14)

| Attempt | Result |
|---|---|
| **Manual tape-measure tool** (`tools/camera-calibration`, Manual tabs) | Exists from September. Needs the robot's true pose at 3 stops: distance to the tag wall at both bumper corners (gives heading and distance), and the sideways offset from the tag centreline (the hard part) |
| **Spin & drive** auto-calibration (`CalibrateCameras` auto + Quick tab): the robot spins and drives in front of a tag with vision corrections off; the tool solves the mount from camera motion vs wheel/gyro motion | Built and tested on simulated data (errors of a few mm, 0.2 deg). On the robot: not repeatable, residuals ~52 mm, and the answer disagreed with the tape (below) |
| **Tape-measure the cameras** | Lens 28.5 in high, 14.5 in behind the front bumper, 5.5 in in from the side bumper edge, robot 33 in square including 3.25 in bumpers |
| **Aim check** (crosshair on a wall, robot 72 in from it) | Left crosshair 69 in high, right 68.5 in; crosshairs 13 in apart and *crossed* ("cross-eyed"). Gives pitch 25.1 / 24.8 deg up and yaw about 11.4 deg inward each, if symmetric. They are **not** symmetric about the centreline by eye, and the centreline is hard to find |

Tape / aim truth against the robot code and the tool:

| | Tape / aim | Robot code | Spin & drive said |
|---|---|---|---|
| x forward of centre | +2.0 in | 2.19 | 2.0 / 2.4 |
| y sideways | +-11.0 in | +-10.91 | 10.9 / -9.8 |
| z height | 28.5 in | 28.7 | **24.0 / 23.6** |
| pitch | 25.1 / 24.8 up (-25) | -25 | **-28.6 / -28.2** |
| yaw (inward) | ~11.4 (assumed symmetric) | -10 / +10 | **-5.8 / +19.4** |

## What we learned

- **Spin & drive is limited by the vision, not the robot's motion.** A pair of tags 14 in apart, 2 m
  away, is only 15 deg wide: rotation and translation are hard to tell apart, and a 6 mm spacing error
  (14.25 in measured vs 14.0 in in the layout) is a 1.7% scale error across it. Left and right cameras
  disagreed with each other by up to 20% on how far the same drive moved. The report's
  standing-still, drive and tape sections exist to expose this.
- **Odometry-vs-vision cannot say which one is wrong.** When they disagree the tool cannot tell.
  Independent truth (tape, aim, a known path) is what settles it.
- **Wheel odometry looks about 10% long** (fitted scale 0.88-0.90, hitting the old limit), and the
  wheels reported ~20-30% more distance than commanded speed x time. Unresolved: `TunerConstants` is
  still the 2026 file (`TODO(2027)`, wheel radius 1.75 in). Check by driving a taped 3 m.
- **The crosshair aim check is a good idea.** It needs only a wall, a tape and the PhotonVision stream,
  and gives pitch and yaw directly. It is limited by how well we know the robot's centreline and
  heading, which is the open problem below.
- **Decimate matters for this:** calibration runs should use decimate 1 (mount calibration does not
  depend on it). We ran decimate 1 at about 65 results/s.

## The open problem: a trustworthy reference for the robot's centreline and heading

Everything above is blocked by one thing. To say "this camera points 11.4 deg inward" we need to know
which way the robot points and where its centreline is, to a fraction of a degree and a few mm, with
the robot a few metres from the target. Ideas, roughly from least to most effort:

1. **A floor line.** Stick a straight line of tape on the floor, perpendicular to the wall (a 3-4-5
   triangle with tape, or a large framing square). Put a small mark at the **front-centre and
   rear-centre of the bumpers** (measure 16.5 in from the side of a 33 in robot, once, and mark it).
   Line both marks up on the tape line: the robot's centreline *is* the line, heading is exact, and
   anything on the wall can be measured from the line's end. Cheap, and it makes the existing
   crosshair and manual tests accurate.
2. **A cross-line laser on the robot centre mark** (a self-levelling cross laser is cheap).
   The vertical laser line on the whiteboard marks the robot's centreline at the wall. Measure each
   crosshair from the line. Limited by how well the laser's beam is squared to the robot (a few tenths
   of a degree is about 0.5 in at 6 ft); square it against the bumper face.
3. **The robot against the wall.** With the front bumper flat on the wall, the heading is exact and the
   lateral position is read off a mark (the bumper-centre mark against a wall mark below the tag).
   Then **back straight off the wall along the floor line** with the tag in view. The path is a known
   straight line perpendicular to the wall, so every camera pose along it can be compared with
   *truth*, not just with odometry, and errors that grow with range (scale, intrinsics) show up as a
   curve. Camera sees the tag from about 20 in out. This is a calibration run with ground truth
   built in; it needs a small "WallBackOff" command (drive straight back at constant speed) and a
   tool view of camera pose vs distance from the wall.
4. **Static truth stops** (the Manual tabs): 3-5 taped positions at 1.5 / 2 / 3 m, centred and
   0.5 m off. Works, but needs the floor line for the sideways part to be quick.
5. **A better target.** More tags, spread wide, with their positions tape-measured into a lab layout
   file. Improves everything that depends on vision (the failure we saw). Check the single-tag vs pair
   consistency first (tag 9 only, tag 10 only, both).
6. **A ceiling reference or an extra camera** to say where the robot is: possible, but we do not want
   a camera on the robot, and it is more setup than (1)-(3).

**Suggested order when we come back:** (1) the floor line and bumper marks (an hour once, then
reusable), then redo the aim check and one static-truth stop with it; then (3) the wall back-off run,
which tests range-dependent vision error with real truth; then (5) if the pair is the limit.

## Also parked

- Per-camera yaw split: only the 13 in crosshair separation was measured, not each crosshair's
  position from the centreline. The floor line fixes this.
- Roll: assumed 0 (3D-printed housing). The tool can solve it, but a bad vision makes that unreliable.
- Wheel radius / gyro check by tape (drive 3 m, 10 spins).
- Recording the tag layout actually installed in the lab (spacing is 14.25 in, layout says 14.0).
- Whether a 1280x800 calibration would help (needs PhotonVision calibrated at that size first).

## Decision (2026-11-14)

Keep the constants in `VisionConstants.java`. Do **not** apply the spin & drive z, pitch or yaw. Treat
the crossover experiment's camera mounts as good enough for now (the left/right swap design cancels
most mount error anyway), and revisit this when we have a reference for the centreline.
