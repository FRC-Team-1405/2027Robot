PS C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor> .\Bootstrap-OrangePi.ps1 LeftPi
Bootstrap-OrangePi 2026-10-20.1 - guided one-time setup of a team Orange Pi (runs on this laptop)
Not to be confused with setup-orangepi.sh, which runs ON the Pi - this script drives it for you.

==============================================================================
Step 1/11: Preflight
==============================================================================
  Why:  Everything below uses the Windows OpenSSH client (ssh, scp, ssh-keygen) and the files in this folder.
  [PASS] ssh, scp and ssh-keygen are available.
         ssh: C:\WINDOWS\System32\OpenSSH\ssh.exe
         scp: C:\WINDOWS\System32\OpenSSH\scp.exe
         ssh-keygen: C:\WINDOWS\System32\OpenSSH\ssh-keygen.exe
         OpenSSH_for_Windows_9.5p2, LibreSSL 3.8.2
  [PASS] Coprocessor files found in C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor

==============================================================================
Step 2/11: Find the Pi
==============================================================================
  Why:  We need the Pi's network address. A Pi plugged straight into the laptop's USB-Ethernet dongle only gets one if Windows Internet Connection Sharing (ICS) is on.
  Doing: Checking the address you gave: LeftPi
  [PASS] SSH answers at LeftPi

==============================================================================
Step 3/11: SSH key login
==============================================================================
  Why:  Key-based login lets the rest of this script (and later tooling) run without typing the Pi password again.
  [PASS] Using existing key C:\Users\FinneyRobotics\.ssh\id_ed25519_orangepi
  Doing: Testing key login as pi@LeftPi ...
  [PASS] Key login already works.

==============================================================================
Step 4/11: Passwordless sudo
==============================================================================
  Why:  The Pi installer needs sudo for apt, systemd units and /etc. Passwordless sudo for this account lets it run unattended.
  [PASS] sudo already works without a password.

==============================================================================
Step 5/11: Pi health check
==============================================================================
  Why:  Confirms OS, Python, free disk, and whether the Pi can reach the internet (apt/pip need it for the first install only).
         hostname leftpi | Ubuntu 24.04.1 LTS | Python 3.12.3 | 12G free | clock 2026-10-21T10:23:20Z
  [WARN] No internet on the Pi, but the venv already has ntcore - the installer can reuse it.
  [WARN] Pi clock differs from this laptop by 1,498,926 s (normal off the robot network; the recorder labels sessions from the roboRIO clock).

==============================================================================
Step 6/11: Camera and PhotonVision streams
==============================================================================
  Why:  The recorder taps PhotonVision's own RAW MJPEG stream, so the camera must be activated in PhotonVision first.
         USB devices: Bus 003 Device 002: ID 0c45:6366 Microdia Webcam Vitade AF
  [PASS] PhotonVision is serving streams on port(s): 1181, 1182
         Raw (input) stream ports by PhotonVision's numbering: 1181
         Please confirm in the dashboard: set Stream Display to RAW and check the <img> URL port (http://LeftPi:5800/#/dashboard).

==============================================================================
Step 7/11: PhotonVision team number
==============================================================================
  Why:  PhotonVision must know team 1405 so it connects to the roboRIO's NetworkTables on the robot.
  [PASS] PhotonVision team number is 1405.

==============================================================================
Step 8/11: Decide this board's identity
==============================================================================
  Why:  Every board on the robot needs a DISTINCT NetworkTables name, and each camera needs a name and its RAW stream URL.
         Examples: LeftPi, RightPi, VisionFront, BenchPi. Letters, digits, _ and - only.
  ? Board NT name [LeftPi]:
         Camera instance names for THIS board (the recordings folder is named after it), e.g. left, right, front.
  ? Camera instance name(s), space separated: LeftCam
  ? RAW stream URL for 'LeftCam' (as the Pi sees it) [http://localhost:1181/stream.mjpg]:

         Board NT name : LeftPi  (metrics at /OrangePi/LeftPi/)
         Camera 'LeftCam'  : http://localhost:1181/stream.mjpg  -> recordings in ~/vision-recordings/LeftCam/
  ? Install with these settings? [Y/n]: y

==============================================================================
Step 9/11: Copy the coprocessor scripts
==============================================================================
  Why:  Puts the scripts and unit files where the installer expects them: /home/pi/coprocessor.
         Also copied 6 simulation file(s) to coprocessor/sim/.
  [PASS] Copied. On the Pi: README.md check-fan.sh enable-fan.sh orangepi-nt-publisher.py orangepi-nt-publisher.service orangepi-vision-recorder.py orangepi-vision-recorder@.service setup-orangepi.sh sim

==============================================================================
Step 10/11: Run the Pi installer
==============================================================================
  Why:  Runs setup-orangepi.sh unattended: creates the Python venv, installs pyntcore, installs and starts the services.
  Doing: Installing (first run downloads packages; this can take a few minutes)...
         Metrics namespace: /OrangePi/LeftPi/
         ntcore import: OK
         Stream responds: http://localhost:1181/stream.mjpg (multipart/x-mixed-replace;boundary=boundarydonotcross)
         ntcore import: OK
         Warning: some journal files were not opened due to insufficient permissions.
         Setup checks passed. Verify /OrangePi updates in NT, raw frames while enabled,
  [PASS] Installer finished without errors.

==============================================================================
Step 11/11: Verify the install
==============================================================================
  Why:  Independent checks that the services are running with the right settings.
  [PASS] setup-orangepi.sh --status reports healthy.
  [PASS] orangepi-nt-publisher.service: active, enabled at boot, restarts=0
  [PASS] orangepi-vision-recorder@LeftCam.service: active, enabled at boot, restarts=0
         LeftCam.env -> CAMERA_STREAM_URL=http://localhost:1181/stream.mjpg; RECORDINGS_DIR=/home/pi/vision-recordings

==============================================================================
Summary
==============================================================================
   1  PASS    Preflight                  OpenSSH + repo files present
   2  PASS    Find the Pi                LeftPi
   3  PASS    SSH key                    key login works
   4  PASS    sudo                       passwordless
   5  PASS    Health                     Ubuntu 24.04.1 LTS; 12G free; internet=False
   6  PASS    Camera                     streams on 1181,1182
   7  PASS    PhotonVision team          1405
   8  PASS    Plan                       LeftPi; cameras: LeftCam
   9  PASS    Copy                       8 files
  10  PASS    Install                    setup-orangepi.sh ok
  11  PASS    Verify                     services healthy

  This Pi is set up.
         Pi: pi@LeftPi   key: C:\Users\FinneyRobotics\.ssh\id_ed25519_orangepi
         Next: bench-verify the recorder with no robot using coprocessor\sim\Run-SimulatedMatch.ps1 (see coprocessor\sim\README.md).
         When done with the Pi, switch Internet Connection Sharing off again.
PS C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor> .\Bootstrap-OrangePi.ps1 RightPi
Bootstrap-OrangePi 2026-10-20.1 - guided one-time setup of a team Orange Pi (runs on this laptop)
Not to be confused with setup-orangepi.sh, which runs ON the Pi - this script drives it for you.

==============================================================================
Step 1/11: Preflight
==============================================================================
  Why:  Everything below uses the Windows OpenSSH client (ssh, scp, ssh-keygen) and the files in this folder.
  [PASS] ssh, scp and ssh-keygen are available.
         ssh: C:\WINDOWS\System32\OpenSSH\ssh.exe
         scp: C:\WINDOWS\System32\OpenSSH\scp.exe
         ssh-keygen: C:\WINDOWS\System32\OpenSSH\ssh-keygen.exe
         OpenSSH_for_Windows_9.5p2, LibreSSL 3.8.2
  [PASS] Coprocessor files found in C:\Users\FinneyRobotics\VS Code\2027Robot\coprocessor

==============================================================================
Step 2/11: Find the Pi
==============================================================================
  Why:  We need the Pi's network address. A Pi plugged straight into the laptop's USB-Ethernet dongle only gets one if Windows Internet Connection Sharing (ICS) is on.
  Doing: Checking the address you gave: RightPi
  [PASS] SSH answers at RightPi

==============================================================================
Step 3/11: SSH key login
==============================================================================
  Why:  Key-based login lets the rest of this script (and later tooling) run without typing the Pi password again.
  [PASS] Using existing key C:\Users\FinneyRobotics\.ssh\id_ed25519_orangepi
  Doing: Testing key login as pi@RightPi ...
  [PASS] Key login already works.

==============================================================================
Step 4/11: Passwordless sudo
==============================================================================
  Why:  The Pi installer needs sudo for apt, systemd units and /etc. Passwordless sudo for this account lets it run unattended.
  [PASS] sudo already works without a password.

==============================================================================
Step 5/11: Pi health check
==============================================================================
  Why:  Confirms OS, Python, free disk, and whether the Pi can reach the internet (apt/pip need it for the first install only).
         hostname RightPi | Ubuntu 24.04.4 LTS | Python 3.12.3 | 11G free | clock 2026-10-04T16:17:27Z
  [WARN] No internet on the Pi, but the venv already has ntcore - the installer can reuse it.
  [WARN] Pi clock differs from this laptop by 2,946,533 s (normal off the robot network; the recorder labels sessions from the roboRIO clock).

==============================================================================
Step 6/11: Camera and PhotonVision streams
==============================================================================
  Why:  The recorder taps PhotonVision's own RAW MJPEG stream, so the camera must be activated in PhotonVision first.
         USB devices: Bus 003 Device 002: ID 0c45:6366 Microdia Webcam Vitade AF
  [PASS] PhotonVision is serving streams on port(s): 1181, 1182
         Raw (input) stream ports by PhotonVision's numbering: 1181
         Please confirm in the dashboard: set Stream Display to RAW and check the <img> URL port (http://RightPi:5800/#/dashboard).

==============================================================================
Step 7/11: PhotonVision team number
==============================================================================
  Why:  PhotonVision must know team 1405 so it connects to the roboRIO's NetworkTables on the robot.
  [PASS] PhotonVision team number is 1405.

==============================================================================
Step 8/11: Decide this board's identity
==============================================================================
  Why:  Every board on the robot needs a DISTINCT NetworkTables name, and each camera needs a name and its RAW stream URL.
         Examples: LeftPi, RightPi, VisionFront, BenchPi. Letters, digits, _ and - only.
  ? Board NT name [RightPi]:
         Camera instance names for THIS board (the recordings folder is named after it), e.g. left, right, front.
  ? Camera instance name(s), space separated: RightCam
  ? RAW stream URL for 'RightCam' (as the Pi sees it) [http://localhost:1181/stream.mjpg]:

         Board NT name : RightPi  (metrics at /OrangePi/RightPi/)
         Camera 'RightCam'  : http://localhost:1181/stream.mjpg  -> recordings in ~/vision-recordings/RightCam/
  ? Install with these settings? [Y/n]: y

==============================================================================
Step 9/11: Copy the coprocessor scripts
==============================================================================
  Why:  Puts the scripts and unit files where the installer expects them: /home/pi/coprocessor.
         Also copied 6 simulation file(s) to coprocessor/sim/.
  [PASS] Copied. On the Pi: Bootstrap-OrangePi.ps1 README.md check-fan.sh enable-fan.sh orangepi-nt-publisher.py orangepi-nt-publisher.service orangepi-vision-recorder.py orangepi-vision-recorder@.service setup-orangepi.sh sim sync-to-orangepi.bat tests

==============================================================================
Step 10/11: Run the Pi installer
==============================================================================
  Why:  Runs setup-orangepi.sh unattended: creates the Python venv, installs pyntcore, installs and starts the services.
  Doing: Installing (first run downloads packages; this can take a few minutes)...
         Metrics namespace: /OrangePi/RightPi/
         ntcore import: OK
         Stream responds: http://rightpi.local:1181/stream.mjpg (multipart/x-mixed-replace;boundary=boundarydonotcross)
         ntcore import: OK
         Warning: some journal files were not opened due to insufficient permissions.
         Setup checks passed. Verify /OrangePi updates in NT, raw frames while enabled,
  [PASS] Installer finished without errors.

==============================================================================
Step 11/11: Verify the install
==============================================================================
  Why:  Independent checks that the services are running with the right settings.
  [PASS] setup-orangepi.sh --status reports healthy.
  [PASS] orangepi-nt-publisher.service: active, enabled at boot, restarts=0
  [PASS] orangepi-vision-recorder@RightCam.service: active, enabled at boot, restarts=0
         RightCam.env -> CAMERA_STREAM_URL=http://rightpi.local:1181/stream.mjpg; RECORDINGS_DIR=/home/pi/vision-recordings

==============================================================================
Summary
==============================================================================
   1  PASS    Preflight                  OpenSSH + repo files present
   2  PASS    Find the Pi                RightPi
   3  PASS    SSH key                    key login works
   4  PASS    sudo                       passwordless
   5  PASS    Health                     Ubuntu 24.04.4 LTS; 11G free; internet=False
   6  PASS    Camera                     streams on 1181,1182
   7  PASS    PhotonVision team          1405
   8  PASS    Plan                       RightPi; cameras: RightCam
   9  PASS    Copy                       8 files
  10  PASS    Install                    setup-orangepi.sh ok
  11  PASS    Verify                     services healthy

  This Pi is set up.
         Pi: pi@RightPi   key: C:\Users\FinneyRobotics\.ssh\id_ed25519_orangepi
         Next: bench-verify the recorder with no robot using coprocessor\sim\Run-SimulatedMatch.ps1 (see coprocessor\sim\README.md).
         When done with the Pi, switch Internet Connection Sharing off again.