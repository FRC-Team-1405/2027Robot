TODO: i think visionRecorder is causing problems with its naming convention that the pictures are not sorted in order by default in the windows file explorer because of the file names. can we improve the naming slugs so they sort by default properly?

today i deployed the updated camera intrinsics and then ran the circle facing tag auto.

that recorded this: akit_26-09-15_22-01-04_visionRecorder1

i updated the left camera config:
- auto exposure: True -> False
- Brightness: ~50 -> 0
- camera gain: ~50 -> 25

then recorded: akit_26-09-15_23-08-34_visionRecorder2


Current AprilTag Camera Configs:
- Target family: AprilTag 36h11 (6.5in)
- Decimate: 3
- Blur: 0
- Threads: 7
- Decision Margin Cutoff: 30
- Pose Estimation Iterations: 100
- Refine Edges: True

Adjusted AprilTag Camera Configs:
- Decimate: 3 -> 1

then recorded: akit_26-09-15_23-55-34_visionRecorder3