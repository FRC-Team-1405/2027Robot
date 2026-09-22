Current pose estimation strategy:
        poseEstimator = new PhotonPoseEstimator(
                AprilTags.getAprilTagFieldLayout(), PoseStrategy.MULTI_TAG_PNP_ON_COPROCESSOR, this.robotToCamera);
        poseEstimator.setTagModel(TargetModel.kAprilTag36h11);
        poseEstimator.setMultiTagFallbackStrategy(PoseStrategy.LOWEST_AMBIGUITY);


New pose estimation strategy:
    poseEstimator = new PhotonPoseEstimator(
        AprilTags.getAprilTagFieldLayout(), PoseStrategy.MULTI_TAG_PNP_ON_RIO, this.robotToCamera);


recorded: akit_26-09-19_15-29-36_MULTI_TAG_PNP_ON_RIO.wpilog


change to lowest ambiguity:
        poseEstimator = new PhotonPoseEstimator(
                AprilTags.getAprilTagFieldLayout(), PoseStrategy.LOWEST_AMBIGUITY, this.robotToCamera);
        poseEstimator.setTagModel(TargetModel.kAprilTag36h11);
        poseEstimator.setMultiTagFallbackStrategy(PoseStrategy.LOWEST_AMBIGUITY);

recorded: akit_26-09-19_15-38-07_LOWEST_AMBIGUITY


TODO: improve vision recorder system. orange pi date time isn't updated when its offline, no battery. can we mark the folder names with some sort of marker when the pi restarts? how can we correlate pi-time to EST?

pi@photonvision:~$ ls -la vision-recordings/
total 484
drwxr-xr-x 30 root root   4096 Jul 15 16:57 .
drwxr-x---  7 pi   pi     4096 Jul 15 13:26 ..
drwxr-xr-x  2 root root   4096 Jul 15 13:04 20260715-130404
drwxr-xr-x  2 root root   4096 Jul 15 13:09 20260715-130851
drwxr-xr-x  2 root root   4096 Jul 15 13:18 20260715-131820
drwxr-xr-x  2 root root   4096 Jul 15 13:22 20260715-132151
drwxr-xr-x  2 root root   4096 Jul 15 13:22 20260715-132206
drwxr-xr-x  2 root root   4096 Jul 15 13:27 20260715-132746
drwxr-xr-x  2 root root  20480 Jul 15 13:28 20260715-132811
drwxr-xr-x  2 root root   4096 Jul 15 13:34 20260715-133430
drwxr-xr-x  2 root root  20480 Jul 15 13:35 20260715-133450
drwxr-xr-x  2 root root  12288 Jul 15 13:44 20260715-134446
drwxr-xr-x  2 root root  36864 Jul 15 13:46 20260715-134516
drwxr-xr-x  2 root root  12288 Jul 15 14:29 20260715-142924
drwxr-xr-x  2 root root  24576 Jul 15 14:30 20260715-143027
drwxr-xr-x  2 root root  12288 Jul 15 14:52 20260715-145226
drwxr-xr-x  2 root root  20480 Jul 15 14:53 20260715-145253
drwxr-xr-x  2 root root  12288 Jul 15 15:32 20260715-153218
drwxr-xr-x  2 root root  20480 Jul 15 15:39 20260715-153856
drwxr-xr-x  2 root root   4096 Jul 15 15:54 20260715-155401
drwxr-xr-x  2 root root   4096 Jul 15 15:54 20260715-155419
drwxr-xr-x  2 root root   4096 Jul 15 15:54 20260715-155431
drwxr-xr-x  2 root root   4096 Jul 15 15:54 20260715-155442
drwxr-xr-x  2 root root  40960 Jul 15 16:00 20260715-155851
drwxr-xr-x  2 root root  12288 Jul 15 16:14 20260715-161445
drwxr-xr-x  2 root root  20480 Jul 15 16:27 20260715-162721
drwxr-xr-x  2 root root  12288 Jul 15 16:36 20260715-163548
drwxr-xr-x  2 root root  20480 Jul 15 16:38 20260715-163748
drwxr-xr-x  2 root root  20480 Jul 15 16:54 20260715-165434
drwxr-xr-x  2 root root 110592 Jul 15 17:00 20260715-165746
pi@photonvision:~$ sudo systemctl status orangepi-vision-recorder.service
● orangepi-vision-recorder.service - Orange Pi raw-frame recorder for post-match vision diagnosis
     Loaded: loaded (/etc/systemd/system/orangepi-vision-recorder.service; enabled; preset: enabled)
     Active: active (running) since Wed 2026-07-15 15:52:52 UTC; 1h 32min ago
   Main PID: 855 (python3)
      Tasks: 7 (limit: 18804)
     Memory: 130.3M (peak: 131.8M)
        CPU: 28.123s
     CGroup: /system.slice/orangepi-vision-recorder.service
             └─855 /home/pi/.venv-ntpublisher/bin/python3 /home/pi/orangepi-vision-recorder.py

Jul 15 16:27:21 photonvision python3[855]: Enabled — starting session /home/pi/vision-recordings/20260715-162721
Jul 15 16:27:43 photonvision python3[855]: Disabled — session ended
Jul 15 16:35:48 photonvision python3[855]: Enabled — starting session /home/pi/vision-recordings/20260715-163548
Jul 15 16:36:00 photonvision python3[855]: Disabled — session ended
Jul 15 16:37:48 photonvision python3[855]: Enabled — starting session /home/pi/vision-recordings/20260715-163748
Jul 15 16:38:10 photonvision python3[855]: Disabled — session ended
Jul 15 16:54:34 photonvision python3[855]: Enabled — starting session /home/pi/vision-recordings/20260715-165434
Jul 15 16:54:58 photonvision python3[855]: Disabled — session ended
Jul 15 16:57:46 photonvision python3[855]: Enabled — starting session /home/pi/vision-recordings/20260715-165746
Jul 15 17:00:33 photonvision python3[855]: Disabled — session ended