pi@photonvision:~/coprocessor$ bash setup-orangepi.sh
Orange Pi setup: team 1405; shared Python venv; systemd services.
Login: pi; home: /home/pi; source: /home/pi/coprocessor
1) Metrics publisher  2) Camera recorders  3) Both  4) Quit
Install which services? [3]
Install/update selected scripts and units, and restart selected services? [y/N] y
Every board on the robot must have a DISTINCT NetworkTables name.
Examples only: LeftPi, RightPi, VisionFront, PracticePi. No board count is assumed.
Board NT name (letters, digits, _ or -) [Right]:
Metrics namespace: /OrangePi/Right/
Setup cannot compare names on other boards; use a different name on each.
ntcore import: OK
Choose only the camera instances hosted on THIS board.
Existing installed recorder instances: orangepi-vision-recorder@right.service
Examples: left  OR  right  OR  front rear  OR  left right. Blank skips recorders.
Camera instances to install/update (space separated): Right
Confirm the Right camera RAW stream in PhotonVision's dashboard first.
Use the RAW stream on THIS board; ports depend on its camera configuration.
Confirmed raw MJPEG URL for Right (no default; blank skips camera): http://photonvision.local:1181/stream.mjpg
Stream responds: http://photonvision.local:1181/stream.mjpg (multipart/x-mixed-replace;boundary=boundarydonotcross)

--- orangepi-nt-publisher.service ---
● orangepi-nt-publisher.service - Orange Pi NT4 metrics publisher
     Loaded: loaded (/etc/systemd/system/orangepi-nt-publisher.service; enabled; preset: enabled)
     Active: active (running) since Sat 2026-10-03 13:43:35 UTC; 2s ago
   Main PID: 3196 (python3)
      Tasks: 7 (limit: 18804)
     Memory: 9.1M (peak: 9.8M)
        CPU: 101ms
     CGroup: /system.slice/orangepi-nt-publisher.service
             └─3196 /home/pi/.venv-ntpublisher/bin/python3 /home/pi/orangepi-nt-publisher.py

--- orangepi-nt-publisher.service ---
● orangepi-nt-publisher.service - Orange Pi NT4 metrics publisher
     Loaded: loaded (/etc/systemd/system/orangepi-nt-publisher.service; enabled; preset: enabled)
     Active: active (running) since Sat 2026-10-03 13:43:35 UTC; 4s ago
   Main PID: 3196 (python3)
      Tasks: 7 (limit: 18804)
     Memory: 9.1M (peak: 9.9M)
        CPU: 112ms
     CGroup: /system.slice/orangepi-nt-publisher.service
             └─3196 /home/pi/.venv-ntpublisher/bin/python3 /home/pi/orangepi-nt-publisher.py

--- orangepi-nt-publisher.service ---
● orangepi-nt-publisher.service - Orange Pi NT4 metrics publisher
     Loaded: loaded (/etc/systemd/system/orangepi-nt-publisher.service; enabled; preset: enabled)
     Active: active (running) since Sat 2026-10-03 13:43:35 UTC; 6s ago
   Main PID: 3196 (python3)
      Tasks: 7 (limit: 18804)
     Memory: 9.1M (peak: 9.9M)
        CPU: 126ms
     CGroup: /system.slice/orangepi-nt-publisher.service
             └─3196 /home/pi/.venv-ntpublisher/bin/python3 /home/pi/orangepi-nt-publisher.py
Created symlink /etc/systemd/system/multi-user.target.wants/orangepi-vision-recorder@Right.service → /etc/systemd/system/orangepi-vision-recorder@.service.

--- orangepi-vision-recorder@Right.service ---
● orangepi-vision-recorder@Right.service - Orange Pi raw-frame recorder for post-match vision diagnosis (Right camera)
     Loaded: loaded (/etc/systemd/system/orangepi-vision-recorder@.service; enabled; preset: enabled)
     Active: active (running) since Sat 2026-10-03 13:43:41 UTC; 2s ago
   Main PID: 3290 (python3)
      Tasks: 7 (limit: 18804)
     Memory: 13.3M (peak: 14.5M)
        CPU: 114ms
     CGroup: /system.slice/system-orangepi\x2dvision\x2drecorder.slice/orangepi-vision-recorder@Right.service
             └─3290 /home/pi/.venv-ntpublisher/bin/python3 /home/pi/orangepi-vision-recorder.py

--- orangepi-vision-recorder@Right.service ---
● orangepi-vision-recorder@Right.service - Orange Pi raw-frame recorder for post-match vision diagnosis (Right camera)
     Loaded: loaded (/etc/systemd/system/orangepi-vision-recorder@.service; enabled; preset: enabled)
     Active: active (running) since Sat 2026-10-03 13:43:41 UTC; 4s ago
   Main PID: 3290 (python3)
      Tasks: 7 (limit: 18804)
     Memory: 13.3M (peak: 14.5M)
        CPU: 115ms
     CGroup: /system.slice/system-orangepi\x2dvision\x2drecorder.slice/orangepi-vision-recorder@Right.service
             └─3290 /home/pi/.venv-ntpublisher/bin/python3 /home/pi/orangepi-vision-recorder.py

--- orangepi-vision-recorder@Right.service ---
● orangepi-vision-recorder@Right.service - Orange Pi raw-frame recorder for post-match vision diagnosis (Right camera)
     Loaded: loaded (/etc/systemd/system/orangepi-vision-recorder@.service; enabled; preset: enabled)
     Active: active (running) since Sat 2026-10-03 13:43:41 UTC; 6s ago
   Main PID: 3290 (python3)
      Tasks: 7 (limit: 18804)
     Memory: 13.3M (peak: 14.5M)
        CPU: 117ms
     CGroup: /system.slice/system-orangepi\x2dvision\x2drecorder.slice/orangepi-vision-recorder@Right.service
             └─3290 /home/pi/.venv-ntpublisher/bin/python3 /home/pi/orangepi-vision-recorder.py
Python environment: /home/pi/.venv-ntpublisher
ntcore import: OK
Filesystem      Size  Used Avail Use% Mounted on
/dev/mmcblk1p2   15G  3.1G   11G  23% /
Board identity: Right; metrics topics: /OrangePi/Right/

--- photonvision.service ---
● photonvision.service - Service that runs PhotonVision
     Loaded: loaded (/etc/systemd/system/photonvision.service; enabled; preset: enabled)
     Active: active (running) since Wed 2026-09-30 00:45:57 UTC; 3 days ago
   Main PID: 815 (java)
      Tasks: 75 (limit: 18804)
     Memory: 405.2M (peak: 454.5M)
        CPU: 17min 11.906s
     CGroup: /system.slice/photonvision.service
             └─815 /usr/bin/java -Xmx512m -jar /opt/photonvision/photonvision.jar

Warning: some journal files were not opened due to insufficient permissions.

--- orangepi-nt-publisher.service ---
● orangepi-nt-publisher.service - Orange Pi NT4 metrics publisher
     Loaded: loaded (/etc/systemd/system/orangepi-nt-publisher.service; enabled; preset: enabled)
     Active: active (running) since Sat 2026-10-03 13:43:35 UTC; 13s ago
   Main PID: 3196 (python3)
      Tasks: 7 (limit: 18804)
     Memory: 9.1M (peak: 9.9M)
        CPU: 168ms
     CGroup: /system.slice/orangepi-nt-publisher.service
             └─3196 /home/pi/.venv-ntpublisher/bin/python3 /home/pi/orangepi-nt-publisher.py
NRestarts=0
ExecStart={ path=/home/pi/.venv-ntpublisher/bin/python3 ; argv[]=/home/pi/.ven>
EnvironmentFiles=/etc/default/orangepi-nt-publisher (ignore_errors=yes)
lines 1-3/3 (END)
NRestarts=0
ExecStart={ path=/home/pi/.venv-ntpublisher/bin/python3 ; argv[]=/home/pi/.venv-ntpublisher/bin/python3 /home/pi/orangepi-nt-publisher.py ; ignore_errors=no ; sta>
EnvironmentFiles=/etc/default/orangepi-nt-publisher (ignore_errors=yes)

--- orangepi-vision-recorder@Right.service ---
● orangepi-vision-recorder@Right.service - Orange Pi raw-frame recorder for post-match vision diagnosis (Right camera)
     Loaded: loaded (/etc/systemd/system/orangepi-vision-recorder@.service; enabled; preset: enabled)
     Active: active (running) since Sat 2026-10-03 13:43:41 UTC; 15s ago
   Main PID: 3290 (python3)
      Tasks: 7 (limit: 18804)
     Memory: 13.3M (peak: 14.5M)
        CPU: 129ms
     CGroup: /system.slice/system-orangepi\x2dvision\x2drecorder.slice/orangepi-vision-recorder@Right.service
             └─3290 /home/pi/.venv-ntpublisher/bin/python3 /home/pi/orangepi-vision-recorder.py
NRestarts=0
ExecStart={ path=/home/pi/.venv-ntpublisher/bin/python3 ; argv[]=/home/pi/.venv-ntpublisher/bin/python3 /home/pi/orangepi-vision-recorder.py ; ignore_errors=no ; >
EnvironmentFiles=/etc/default/orangepi-nt-publisher (ignore_errors=yes)
EnvironmentFiles=/etc/orangepi-vision-recorder/Right.env (ignore_errors=no)

--- orangepi-vision-recorder@right.service ---
● orangepi-vision-recorder@right.service - Orange Pi raw-frame recorder for post-match vision diagnosis (right camera)
     Loaded: loaded (/etc/systemd/system/orangepi-vision-recorder@.service; enabled; preset: enabled)
     Active: active (running) since Wed 2026-09-30 00:45:57 UTC; 3 days ago
   Main PID: 821 (python3)
      Tasks: 7 (limit: 18804)
     Memory: 17.1M (peak: 18.1M)
        CPU: 1.065s
     CGroup: /system.slice/system-orangepi\x2dvision\x2drecorder.slice/orangepi-vision-recorder@right.service
             └─821 /home/photon/.venv-ntpublisher/bin/python3 /home/photon/orangepi-vision-recorder.py

Warning: some journal files were not opened due to insufficient permissions.
NRestarts=0
ExecStart={ path=/home/pi/.venv-ntpublisher/bin/python3 ; argv[]=/home/pi/.venv-ntpublisher/bin/python3 /home/pi/orangepi-vision-recorder.py ; ignore_errors=no ; >
EnvironmentFiles=/etc/default/orangepi-nt-publisher (ignore_errors=yes)
EnvironmentFiles=/etc/orangepi-vision-recorder/right.env (ignore_errors=no)
Active services do not prove NT connectivity, raw-camera correctness, or enabled-bit decoding.
Recorder instances not selected for update are kept; to retire one, use:
sudo systemctl disable --now orangepi-vision-recorder@<instance>.service
Setup checks passed. Verify /OrangePi updates in NT, raw frames while enabled,
FMSInfo enabled-bit decoding, and PhotonVision FPS/latency on the bench.
Recorder storage cap is 5GB PER camera; check free space for both cameras.
Disconnect temporary Wi-Fi/internet before returning the Pi to the robot.