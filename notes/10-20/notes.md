i need to determine:
- if orange pi's the best coprocessor to invest in
- i think our camera is the best camera for cheap coverage, but can we get a high quality camera for longer distance/high accuracy (high res) targeting
- is there significant performance improvements running one camera per orange pi vs two camera's per orange pi

it seems that in most matches our orange pi running two camera's was less than 10% ram utilization at all times with 16gb of ram. meaning we could significantly reduce orangePi ram requirements.

# Bootstrap OrangePi Error

PS C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor> .\Bootstrap-OrangePi.ps1
Bootstrap-OrangePi 2026-10-18.1 - guided one-time setup of a team Orange Pi (runs on this laptop)
Not to be confused with setup-orangepi.sh, which runs ON the Pi - this script drives it for you.

==============================================================================
Step 1/11: Preflight
==============================================================================
  Why:  Everything below uses the Windows OpenSSH client (ssh, scp, ssh-keygen) and the files in this folder.
  [PASS] ssh, scp and ssh-keygen are available.
  [PASS] Coprocessor files found in C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor

==============================================================================
Step 2/11: Find the Pi
==============================================================================
  Why:  We need the Pi's network address. A Pi plugged straight into the laptop's USB-Ethernet dongle only gets one if Windows Internet Connection Sharing (ICS) is on.
  Doing: Looking for a Pi (mDNS name, the ICS 192.168.137.x subnet, and the bench address)...
         No 192.168.137.x adapter on this laptop, so Internet Connection Sharing is probably off.
  [PASS] Found a Pi at p

==============================================================================
Step 3/11: SSH key login
==============================================================================
  Why:  Key-based login lets the rest of this script (and later tooling) run without typing the Pi password again.
  Doing: No key at C:\Users\FinneyRobotics\.ssh\id_ed25519_orangepi - creating a new ed25519 key with no passphrase (it is only used for this Pi).
  ? Create it? [Y/n]: y
  [FAIL] ssh-keygen failed: Too many arguments.
usage: ssh-keygen [-q] [-a rounds] [-b bits] [-C comment] [-f output_keyfile]
                  [-m format] [-N new_passphrase] [-O option]
                  [-t dsa | ecdsa | ecdsa-sk | ed25519 | ed25519-sk | rsa]
                  [-w provider] [-Z cipher]
       ssh-keygen -p [-a rounds] [-f keyfile] [-m format] [-N new_passphrase]
                   [-P old_passphrase] [-Z cipher]
       ssh-keygen -i [-f input_keyfile] [-m key_format]
       ssh-keygen -e [-f input_keyfile] [-m key_format]
       ssh-keygen -y [-f input_keyfile]
       ssh-keygen -c [-a rounds] [-C comment] [-f keyfile] [-P passphrase]
       ssh-keygen -l [-v] [-E fingerprint_hash] [-f input_keyfile]
       ssh-keygen -B [-f input_keyfile]
       ssh-keygen -D pkcs11
       ssh-keygen -F hostname [-lv] [-f known_hosts_file]
       ssh-keygen -H [-f known_hosts_file]
       ssh-keygen -K [-a rounds] [-w provider]
       ssh-keygen -R hostname [-f known_hosts_file]
       ssh-keygen -r hostname [-g] [-f input_keyfile]
       ssh-keygen -M generate [-O option] output_file
       ssh-keygen -M screen [-f input_file] [-O option] output_file
       ssh-keygen -I certificate_identity -s ca_key [-hU] [-D pkcs11_provider]
                  [-n principals] [-O option] [-V validity_interval]
                  [-z serial_number] file ...
       ssh-keygen -L [-f input_keyfile]
       ssh-keygen -A [-a rounds] [-f prefix_path]
       ssh-keygen -k -f krl_file [-u] [-s ca_public] [-z version_number]
                  file ...
       ssh-keygen -Q [-l] -f krl_file [file ...]
       ssh-keygen -Y find-principals -s signature_file -f allowed_signers_file
       ssh-keygen -Y match-principals -I signer_identity -f allowed_signers_file
       ssh-keygen -Y check-novalidate -n namespace -s signature_file
       ssh-keygen -Y sign -f key_file -n namespace file [-O option] ...
       ssh-keygen -Y verify -f allowed_signers_file -I signer_identity
                  -n namespace -s signature_file [-r krl_file] [-O option]


  [FAIL] Could not create key.

==============================================================================
Summary
==============================================================================
   1  PASS    Preflight                  OpenSSH + repo files present
   2  PASS    Find the Pi                p
   3  FAIL    SSH key                    keygen failed

  Not finished: fix the FAIL line(s) above and run this script again - it skips what is already done.
         Pi: pi@p   key: C:\Users\FinneyRobotics\.ssh\id_ed25519_orangepi
         Next: bench-verify the recorder with no robot using coprocessor\sim\Run-SimulatedMatch.ps1 (see coprocessor\sim\README.md).
         When done with the Pi, switch Internet Connection Sharing off again.
PS C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor> .\Bootstrap-OrangePi.ps1 --usage
Bootstrap-OrangePi 2026-10-18.1 - guided one-time setup of a team Orange Pi (runs on this laptop)
Not to be confused with setup-orangepi.sh, which runs ON the Pi - this script drives it for you.

==============================================================================
Step 1/11: Preflight
==============================================================================
  Why:  Everything below uses the Windows OpenSSH client (ssh, scp, ssh-keygen) and the files in this folder.
  [PASS] ssh, scp and ssh-keygen are available.
  [PASS] Coprocessor files found in C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor

==============================================================================
Step 2/11: Find the Pi
==============================================================================
  Why:  We need the Pi's network address. A Pi plugged straight into the laptop's USB-Ethernet dongle only gets one if Windows Internet Connection Sharing (ICS) is on.
  Doing: Checking the address you gave: --usage
  [FAIL] Nothing answers on port 22 at --usage.

  [FAIL] Pi not reachable at --usage. Check power, cable, and that the laptop and Pi share a network.

==============================================================================
Summary
==============================================================================
   1  PASS    Preflight                  OpenSSH + repo files present
   2  FAIL    Find the Pi                no SSH at --usage

  Not finished: fix the FAIL line(s) above and run this script again - it skips what is already done.
PS C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor> .\Bootstrap-OrangePi.ps1 photonvision.local
Bootstrap-OrangePi 2026-10-18.1 - guided one-time setup of a team Orange Pi (runs on this laptop)
Not to be confused with setup-orangepi.sh, which runs ON the Pi - this script drives it for you.

==============================================================================
Step 1/11: Preflight
==============================================================================
  Why:  Everything below uses the Windows OpenSSH client (ssh, scp, ssh-keygen) and the files in this folder.
  [PASS] ssh, scp and ssh-keygen are available.
  [PASS] Coprocessor files found in C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor

==============================================================================
Step 2/11: Find the Pi
==============================================================================
  Why:  We need the Pi's network address. A Pi plugged straight into the laptop's USB-Ethernet dongle only gets one if Windows Internet Connection Sharing (ICS) is on.
  Doing: Checking the address you gave: photonvision.local
  [PASS] SSH answers at photonvision.local

==============================================================================
Step 3/11: SSH key login
==============================================================================
  Why:  Key-based login lets the rest of this script (and later tooling) run without typing the Pi password again.
  Doing: No key at C:\Users\FinneyRobotics\.ssh\id_ed25519_orangepi - creating a new ed25519 key with no passphrase (it is only used for this Pi).
  ? Create it? [Y/n]: y
  [FAIL] ssh-keygen failed: Too many arguments.
usage: ssh-keygen [-q] [-a rounds] [-b bits] [-C comment] [-f output_keyfile]
                  [-m format] [-N new_passphrase] [-O option]
                  [-t dsa | ecdsa | ecdsa-sk | ed25519 | ed25519-sk | rsa]
                  [-w provider] [-Z cipher]
       ssh-keygen -p [-a rounds] [-f keyfile] [-m format] [-N new_passphrase]
                   [-P old_passphrase] [-Z cipher]
       ssh-keygen -i [-f input_keyfile] [-m key_format]
       ssh-keygen -e [-f input_keyfile] [-m key_format]
       ssh-keygen -y [-f input_keyfile]
       ssh-keygen -c [-a rounds] [-C comment] [-f keyfile] [-P passphrase]
       ssh-keygen -l [-v] [-E fingerprint_hash] [-f input_keyfile]
       ssh-keygen -B [-f input_keyfile]
       ssh-keygen -D pkcs11
       ssh-keygen -F hostname [-lv] [-f known_hosts_file]
       ssh-keygen -H [-f known_hosts_file]
       ssh-keygen -K [-a rounds] [-w provider]
       ssh-keygen -R hostname [-f known_hosts_file]
       ssh-keygen -r hostname [-g] [-f input_keyfile]
       ssh-keygen -M generate [-O option] output_file
       ssh-keygen -M screen [-f input_file] [-O option] output_file
       ssh-keygen -I certificate_identity -s ca_key [-hU] [-D pkcs11_provider]
                  [-n principals] [-O option] [-V validity_interval]
                  [-z serial_number] file ...
       ssh-keygen -L [-f input_keyfile]
       ssh-keygen -A [-a rounds] [-f prefix_path]
       ssh-keygen -k -f krl_file [-u] [-s ca_public] [-z version_number]
                  file ...
       ssh-keygen -Q [-l] -f krl_file [file ...]
       ssh-keygen -Y find-principals -s signature_file -f allowed_signers_file
       ssh-keygen -Y match-principals -I signer_identity -f allowed_signers_file
       ssh-keygen -Y check-novalidate -n namespace -s signature_file
       ssh-keygen -Y sign -f key_file -n namespace file [-O option] ...
       ssh-keygen -Y verify -f allowed_signers_file -I signer_identity
                  -n namespace -s signature_file [-r krl_file] [-O option]


  [FAIL] Could not create key.

==============================================================================
Summary
==============================================================================
   1  PASS    Preflight                  OpenSSH + repo files present
   2  PASS    Find the Pi                photonvision.local
   3  FAIL    SSH key                    keygen failed

  Not finished: fix the FAIL line(s) above and run this script again - it skips what is already done.
         Pi: pi@photonvision.local   key: C:\Users\FinneyRobotics\.ssh\id_ed25519_orangepi
         Next: bench-verify the recorder with no robot using coprocessor\sim\Run-SimulatedMatch.ps1 (see coprocessor\sim\README.md).
         When done with the Pi, switch Internet Connection Sharing off again.
PS C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor>



# Health Check Live Robot page goes blank after connecting
Uncaught TypeError: Cannot read properties of null (reading 'toFixed')
    at Dt (index-CsBvv-6G.js:9:115117)
    at Eo (index-CsBvv-6G.js:8:47507)
    at _c (index-CsBvv-6G.js:8:69941)
    at Pc (index-CsBvv-6G.js:8:80191)
    at Mu (index-CsBvv-6G.js:8:115514)
    at ku (index-CsBvv-6G.js:8:114598)
    at Ou (index-CsBvv-6G.js:8:114437)
    at gu (index-CsBvv-6G.js:8:111307)
    at cd (index-CsBvv-6G.js:8:122813)
    at MessagePort.ne (index-CsBvv-6G.js:1:9770)
Dt @ index-CsBvv-6G.js:9
Eo @ index-CsBvv-6G.js:8
_c @ index-CsBvv-6G.js:8
Pc @ index-CsBvv-6G.js:8
Mu @ index-CsBvv-6G.js:8
ku @ index-CsBvv-6G.js:8
Ou @ index-CsBvv-6G.js:8
gu @ index-CsBvv-6G.js:8
cd @ index-CsBvv-6G.js:8
ne @ index-CsBvv-6G.js:1
postMessage
T @ index-CsBvv-6G.js:1
e.unstable_scheduleCallback @ index-CsBvv-6G.js:1
sd @ index-CsBvv-6G.js:8
od @ index-CsBvv-6G.js:8
(anonymous) @ index-CsBvv-6G.js:8


# Strange photon vision camera mismatch error
Camera Mismatch Detected! Visit the Camera Matching page for more information. Note: Camera matching is done by USB port. Ensure cameras are plugged into the same USB ports as when they were activated.


# another health check error
Uncaught TypeError: Cannot read properties of null (reading 'toFixed')
    at Dt (index-CsBvv-6G.js:9:115117)
    at Eo (index-CsBvv-6G.js:8:47507)
    at _c (index-CsBvv-6G.js:8:69941)
    at Pc (index-CsBvv-6G.js:8:80191)
    at Mu (index-CsBvv-6G.js:8:115514)
    at ku (index-CsBvv-6G.js:8:114598)
    at Ou (index-CsBvv-6G.js:8:114437)
    at gu (index-CsBvv-6G.js:8:111307)
    at cd (index-CsBvv-6G.js:8:122813)
    at MessagePort.ne (index-CsBvv-6G.js:1:9770)



disabled ENABLE_POWER_TELEMETRY
recorded akit_26-10-21_00-57-37-bundle

disabled PHOENIX_SIGNAL_LOGGING
recorded akit_26-10-21_01-03-57-bundle

enabled LOW_RATE_SHOOTER_DIAGNOSTICS
recorded akit_26-10-21_01-07-50-bundle

enabled ZERO_UNUSED_MECHANISM_STATUS_SIGNALS
recorded akit_26-10-21_01-14-29-bundle
no effect?

enabled ROBOT_DASHBOARD_10_HZ
recorded akit_26-10-21_01-17-36-bundle

enabled SWERVE_TELEMETRY_10_HZ
recorded akit_26-10-21_01-21-36-bundle

disabled LOG_NETWORKTABLES_TO_WPILOG
recorded akit_26-10-21_01-23-34-bundle

a bunch of changes:
    public static final boolean POWER_REQUEST_DETAILS = false;
    public static final boolean COPROCESSOR_HEALTH_LOGGING = false;
    public static final boolean MIRROR_TRACER_TIMINGS = false;
recorded akit_26-10-21_01-32-18-bundle
drastically reduced robot loop times! still almost hit 100ms and i saw the robot jump/drop for a split second when going around in the circle. i'm wondering if that's a loop issue or an odometry update that made it shift quickly

pulled git commit "Reduce repeated bench console warnings and retain loop deadline diagnostics"
recorded akit_26-10-21_01-39-52-bundle

# Analysis of the recordings (done 2026-10-21)

Logs: `C:\Users\importsjc\robotics\logs\10-20\`. Every run from 00:57 on was the same ~20 s auto
(the circle), so the runs compare like for like. Numbers are the Health Check (LogBench) over the
enabled time of the full `akit_*.wpilog`. Each log's `RealMetadata/FeatureSwitches` was checked
against these notes: each deploy changed exactly the switch(es) written above, nothing else.

## How big is the noise?

- **Loop time, run to run: about ±3-4 ms on the mean (±15 %), ±10 ms on the p95**, for one 20 s run.
  The CAN-only changes (LOW_RATE_SHOOTER_DIAGNOSTICS, ZERO_UNUSED_MECHANISM_STATUS_SIGNALS) can't
  change CPU time, yet the mean moved -3.7 ms then +5.7 ms. In those runs *every* subsystem got
  faster or slower together (Hopper, Intake, Pickup, Drivetrain, Indexer: the ones no switch
  touched), so it is the roboRIO as a whole running faster or slower, not the code that changed.
- **One known cause:** LogBench's live Health Check connected as an NetworkTables client starting
  with the 01:14 run, the same run where the loop jumped +5.7 ms with untouched subsystems ~20 %
  slower. Every later run had it connected too, so 01:14 onward compares fairly with itself. Keep the
  same dashboards connected for a whole A/B session (the Health Check now lists them).
- **CAN utilization: ±3 points between runs.** Idle 64-70 % and enabled 74-80 % in every log tonight,
  including the three before the notes start. Peak was 100 % in all of them.
- So: treat a single-run change under ~4 ms mean or ~3 CAN points as noise. The real ones below are
  either much bigger than that or show up directly in their own `Timing/*` entry.

## Change -> effect

| Log | Change | Loop mean | p95 | Loops >20 ms | CAN idle / enabled | Significant? |
|---|---|---|---|---|---|---|
| 00-08-44 | baseline (no switch metadata in this build) | 65.3 ms | 122 ms | 100 % | 70 / 77 % | - |
| 00-57-37 | ENABLE_POWER_TELEMETRY off | **32.7** | 59 | 99 % | 66 / 76 % | **Yes, the biggest win.** PowerTelemetryMs 20.6 -> 0 ms directly; CoprocessorHealthLogger 7.3 -> 1.7 ms also dropped. This deploy was also the first with switch metadata, so part of the 33 ms may be other code in that build. No CAN change (signals were already off). |
| 01-03-57 | PHOENIX_SIGNAL_LOGGING off | 26.7 | 55 | 75 % | 69 / 78 % | **Probably, small.** PhoenixReplayMs 1.2 -> 0 ms directly; the rest of the -6 ms is within noise (the .hoot writer is a background thread, so it may save a bit more). |
| 01-07-50 | LOW_RATE_SHOOTER_DIAGNOSTICS on | 23.0 | 45 | 47 % | 70 / 80 % | **No.** CAN didn't move. The -3.7 ms loop change is noise (untouched subsystems were 17 % faster too). |
| 01-14-29 | ZERO_UNUSED_MECHANISM_STATUS_SIGNALS on | 28.7 | 59 | 89 % | 67 / 77 % | **No** (confirms "no effect?"). CAN -3/-3 points is within noise. The +5.7 ms is LogBench connecting, not this switch. |
| 01-17-36 | ROBOT_DASHBOARD_10_HZ on | 26.2 | 56 | 71 % | 65 / 76 % | **Yes, small.** PublishingMs 2.1 -> 0.7 ms directly. |
| 01-21-36 | SWERVE_TELEMETRY_10_HZ on | 25.1 | 49 | 60 % | 68 / 78 % | **Can't tell.** PublishingMs 0.7 -> 0.55. Telemetry.telemeterize runs on CTRE's odometry thread, not the main loop, so only shows indirectly. Cheap to keep. |
| 01-23-34 | LOG_NETWORKTABLES_TO_WPILOG off | 22.9 | 45 | 35 % | 66 / 77 % | **Maybe.** No timer covers DataLogManager (it's a background thread); -2.2 ms with untouched subsystems ~9 % faster fits a background CPU saving, but one run can't separate it from noise. |
| 01-32-18 | POWER_REQUEST_DETAILS, COPROCESSOR_HEALTH_LOGGING, MIRROR_TRACER_TIMINGS off | 19.0 | 35 | 19 % | 64 / 76 % | **Yes.** TracerMirrorMs 3.8 -> 0 and CoprocessorHealthLoggerMs 1.35 -> 0 (5.1 ms directly). POWER_REQUEST_DETAILS has no timer of its own. |
| 01-39-52 | commit: quiet repeated console warnings (QUIET_JOYSTICK_WARNINGS, QUIET_SCHEDULER_OVERRUN_WARNINGS) | **15.6** | **21.5** | **7 %** | 70 / 77 % | **Yes, mostly in the tail.** Worst loop 97 -> 61 ms. Printing an overrun dump costs time and causes the next overrun, so quieting it breaks that loop. First run with the mean under 20 ms. |

Overall, 00:08 -> 01:39 cut the mean loop from 65 to 15.6 ms (code time per loop 61 -> 12.8 ms), the
p95 from 122 to 21.5 ms and overrunning loops from 100 % to 7 %. **None of the CAN switches changed
CAN utilization.** The ~65 % idle load is from something those switches don't touch. The swerve
(8 TalonFX, 4 CANcoders, Pigeon on the roboRIO bus, `TunerConstants.kCANBus = ""`) is the
main suspect and the next thing to test.

## The jump/drop while driving the circle (01-32-18)

At 38.6 s into that log the main loop stalled: about 260 ms between pose updates, and the run's
largest GC reading (239 ms). The robot kept driving on its last command, so the pose jumped about
0.3 m when the loop came back. Vision then made 15-20 cm corrections (38.7-39.4 s) pulling it back.
So it was a loop stall (very likely a garbage-collection pause), not bad odometry or vision. 01-39-52's
worst pose step was 0.1 m. GC averaged 6.0 ms/loop in 01-32 vs about 3 ms in the other runs.

## Health Check changes made from this

- Loop-time "mean" is now a mean **per loop**. Before, it was time-weighted, so one 100 ms loop counted
  five times as much as a 20 ms loop (the 23:22 log read 103 ms; per loop it's 66 ms). Same for code
  time and the Timing breakdown.
- New rows: **loop time p95**, **share of loops over 20 ms**, **GC time per loop**, **feature switches
  deployed** (from the log, not the laptop), and **NetworkTables clients connected while enabled**,
  so a changed dashboard setup shows up before you trust a difference.

## Next time

- Record each setting twice, or go A-B-A. One run per setting can't separate a 3 ms change from noise.
- Drive at least 60 s enabled per run. The 20 s autos give about 1000 loops, enough for big effects only.
- Connect the same dashboards for the whole session and check the NT clients row matches.
- Compare the untouched subsystems' Timing rows across runs. If they all moved, it's noise.

# console logs examples

plugged in
Loop time of 0.02s overrun
Warning at edu.wpi.first.wpilibj.IterativeRobotBase.printLoopOverrunMessage(IterativeRobotBase.java:436): Loop time of 0.02s overrun
CommandScheduler loop overrun
Hopper.periodic(): 0.000760s
Pickup.periodic(): 0.000241s
CommandSwerveDrivetrain.periodic(): 0.001002s
buttons.run(): 0.000111s
Intake.periodic(): 0.000557s
Vision.periodic(): 0.014246s
Shooter.periodic(): 0.013987s
AdjustableHood.periodic(): 0.000056s
Indexer.periodic(): 0.000352s
Warning at edu.wpi.first.wpilibj.Tracer.lambda$printEpochs$0(Tracer.java:62): Hopper.periodic(): 0.000760s
Pickup.periodic(): 0.000241s
CommandSwerveDrivetrain.periodic(): 0.001002s
buttons.run(): 0.000111s
Intake.periodic(): 0.000557s
Vision.periodic(): 0.014246s
Shooter.periodic(): 0.013987s
AdjustableHood.periodic(): 0.000056s
Indexer.periodic(): 0.000352s
SmartDashboard.updateValues(): 0.000482s
robotPeriodic(): 0.022093s
LiveWindow.updateValues(): 0.000000s
Shuffleboard.update(): 0.000000s
disabledPeriodic(): 0.000223s
Warning at edu.wpi.first.wpilibj.Tracer.lambda$printEpochs$0(Tracer.java:62): SmartDashboard.updateValues(): 0.000482s
robotPeriodic(): 0.022093s
LiveWindow.updateValues(): 0.000000s
Shuffleboard.update(): 0.000000s
disabledPeriodic(): 0.000223s
Joystick POV 0 on port 1 not available, check if controller is plugged in
Warning at edu.wpi.first.wpilibj.DriverStation.reportJoystickUnpluggedWarning(DriverStation.java:1345): Joystick POV 0 on port 1 not available, check if controller is plugged in
Loop time of 0.02s overrun
Warning at edu.wpi.first.wpilibj.IterativeRobotBase.printLoopOverrunMessage(IterativeRobotBase.java:436): Loop time of 0.02s overrun
SmartDashboard.updateValues(): 0.000464s
robotPeriodic(): 0.026156s
LiveWindow.updateValues(): 0.000018s
Shuffleboard.update(): 0.000000s
disabledPeriodic(): 0.000111s
Warning at edu.wpi.first.wpilibj.Tracer.lambda$printEpochs$0(Tracer.java:62): SmartDashboard.updateValues(): 0.000464s
robotPeriodic(): 0.026156s
LiveWindow.updateValues(): 0.000018s
Shuffleboard.update(): 0.000000s
disabledPeriodic(): 0.000111s
Joystick POV 0 on port 1 not available, check if controller is plugged in
Warning at edu.wpi.first.wpilibj.DriverStation.reportJoystickUnpluggedWarning(DriverStation.java:1345): Joystick POV 0 on port 1 not available, check if controller is plugged in
CommandScheduler loop overrun
Hopper.periodic(): 0.000241s
Pickup.periodic(): 0.000260s
CommandSwerveDrivetrain.periodic(): 0.000316s
buttons.run(): 0.010295s
Intake.periodic(): 0.000575s
Vision.periodic(): 0.006270s
Shooter.periodic(): 0.002114s
AdjustableHood.periodic(): 0.000056s
Indexer.periodic(): 0.000389s
Warning at edu.wpi.first.wpilibj.Tracer.lambda$printEpochs$0(Tracer.java:62): Hopper.periodic(): 0.000241s
Pickup.periodic(): 0.000260s
CommandSwerveDrivetrain.periodic(): 0.000316s
buttons.run(): 0.010295s
Intake.periodic(): 0.000575s
Vision.periodic(): 0.006270s
Shooter.periodic(): 0.002114s
AdjustableHood.periodic(): 0.000056s
Indexer.periodic(): 0.000389s
Loop time of 0.02s overrun
Warning at edu.wpi.first.wpilibj.IterativeRobotBase.printLoopOverrunMessage(IterativeRobotBase.java:436): Loop time of 0.02s overrun
SmartDashboard.updateValues(): 0.001076s
robotPeriodic(): 0.034429s
LiveWindow.updateValues(): 0.000000s
Shuffleboard.update(): 0.000000s
disabledPeriodic(): 0.000241s
Warning at edu.wpi.first.wpilibj.Tracer.lambda$printEpochs$0(Tracer.java:62): SmartDashboard.updateValues(): 0.001076s
robotPeriodic(): 0.034429s
LiveWindow.updateValues(): 0.000000s
Shuffleboard.update(): 0.000000s
disabledPeriodic(): 0.000241s
Joystick POV 0 on port 1 not available, check if controller is plugged in
Warning at edu.wpi.first.wpilibj.DriverStation.reportJoystickUnpluggedWarning(DriverStation.java:1345): Joystick POV 0 on port 1 not available, check if controller is plugged in
Loop time of 0.02s overrun
Warning at edu.wpi.first.wpilibj.IterativeRobotBase.printLoopOverrunMessage(IterativeRobotBase.java:436): Loop time of 0.02s overrun