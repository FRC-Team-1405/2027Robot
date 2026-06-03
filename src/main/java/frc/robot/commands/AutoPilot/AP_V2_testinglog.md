i tried the original code and the drivebase turned to the correct heading (or close to it) and then the drive/steer (hard to tell which) started oscilating. but the robot never moved from the start position, just rotated.

then i tried changing the gains:
            private static final Slot0Configs steerGains = new Slot0Configs()
                        .withKP(10).withKI(0).withKD(0.1)
                        .withKS(0.15).withKV(0).withKA(0)
                        .withStaticFeedforwardSign(StaticFeedforwardSignValue.UseClosedLoopSign);
        // When using closed-loop control, the drive motor uses the control
        // output type specified by SwerveModuleConstants.DriveMotorClosedLoopOutput
        private static final Slot0Configs driveGains = new Slot0Configs()
                        .withKP(0.0).withKI(0).withKD(0.0)
                        .withKS(0.0).withKV(0.20).withKA(0);

and dropping the  private double headingKP = 0.2;


this caused the same behavior minus the oscillation. just rotation and then nothing. i could hear very small motor movement sounds but the robot didn't move.
logs at the end:

    vx:-0.026 vy:0.030 spd:0.040 hdg:5.0deg dist:1.434m | rVx:-0.000 rVy:-0.000 fVx:-0.000 fVy:0.000
    vx:-0.026 vy:0.031 spd:0.040 hdg:5.0deg dist:1.434m | rVx:-0.000 rVy:-0.001 fVx:-0.001 fVy:0.000
    vx:-0.026 vy:0.030 spd:0.040 hdg:5.0deg dist:1.434m | rVx:-0.000 rVy:0.000 fVx:0.000 fVy:0.000
    vx:-0.028 vy:0.033 spd:0.043 hdg:5.0deg dist:1.434m | rVx:0.001 rVy:-0.003 fVx:-0.004 fVy:-0.001
    vx:-0.026 vy:0.030 spd:0.040 hdg:5.0deg dist:1.434m | rVx:-0.000 rVy:0.000 fVx:0.000 fVy:0.000
    vx:-0.024 vy:0.028 spd:0.037 hdg:5.0deg dist:1.434m | rVx:-0.004 rVy:0.001 fVx:0.001 fVy:0.004
    vx:-0.026 vy:0.030 spd:0.040 hdg:5.0deg dist:1.434m | rVx:-0.000 rVy:0.000 fVx:0.000 fVy:0.000
    vx:-0.026 vy:0.030 spd:0.040 hdg:5.0deg dist:1.434m | rVx:0.000 rVy:0.000 fVx:0.000 fVy:-0.000
    vx:-0.026 vy:0.030 spd:0.040 hdg:5.0deg dist:1.434m | rVx:-0.000 rVy:0.000 fVx:0.000 fVy:0.000
    END APv2(MoveTo_rightBump_AllianceToFieldStart) | interrupted=true dist=1.434m hdgErr=5.0deg final(14.18,4.48,-95.0deg) target(13.24,5.57,-90.0deg)


i tried changing the steer gains back up and saw oscillation on the steer modules, so i think i also have an issue there.
    .withKP(60).withKI(0).withKD(0.1)
    .withKS(0.15).withKV(0).withKA(0)

i dropped my steer gains back to kP=10,
i bumped up my drive kV even more:
    .withKP(0.0).withKI(0).withKD(0.0)
    .withKS(0.0).withKV(0.8).withKA(0);

this looked better but not great, it rotated cleanly with no chatter, then started moving slowly towards the target and experienced a bit of steer chatter. then reaching the target a lot of chatter when it tried to finally correct the 1deg rotation error.


i bumped my headingKP = 1.0;
i bumped my drive kV=1.6


it spun very fast so i disabled quickly

updated some values
double headingKP = 0.6;
double headingKD = 0.02;

it didn't turn as fast so i let it almost finish the movement. it turned quickly with chatter then drove slowly with no chatter and then accerated at the end (beeline?) and more chatter probably for rotation.

it seems like the rotation is the big issue here. like the heading PID is causing a lot of trouble.

i then realized that kAutopilot.calculate is supposed to take robot relative speeds not field speeds so i updated the call and removed the unnecessary field speeds conversion.

this got me a lot better results. i then noticed that in TunerConstants i had kCoupleRatio = 0; which didn't seem reasonable.

i bumped it up to an estimated kCoupleRatio = 3.5
i need to determine a quick and easy way to get the real value

ok this is really close to being good now. i'm still seeing a lot of chatter around the end of a path. both when i see an april tag and not.

i think the chatter i'm hearing when i do see an april tag could be the vision updating in a weird way. my camera positions aren't exactly correct so they both give a slightly different version of the robot's odometry. i think this causes a bit of movement at the end of a path when it's trying to hit its thresholds.

the other type of chatter i don't understand but seems to be coming from both the drive gains and steer. i see it sometimes jumping the steer module targets around a lot, so fast that the modules barely even move. i also see the drive modules going from small positive to negative vectors, no steer changes.