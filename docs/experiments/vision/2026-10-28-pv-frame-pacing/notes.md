pi@leftpi:~$ sudo v4l2-ctl -d /dev/video0 --list-formats-ext
ioctl: VIDIOC_ENUM_FMT
        Type: Video Capture

        [0]: 'MJPG' (Motion-JPEG, compressed)
                Size: Discrete 1280x800
                        Interval: Discrete 0.008s (120.000 fps)
                        Interval: Discrete 0.010s (100.000 fps)
                Size: Discrete 1280x720
                        Interval: Discrete 0.008s (120.000 fps)
                Size: Discrete 800x600
                        Interval: Discrete 0.008s (120.000 fps)
                        Interval: Discrete 0.010s (100.000 fps)
                Size: Discrete 640x480
                        Interval: Discrete 0.008s (120.000 fps)
                        Interval: Discrete 0.010s (100.000 fps)
                Size: Discrete 320x240
                        Interval: Discrete 0.008s (120.000 fps)
                        Interval: Discrete 0.010s (100.000 fps)
        [1]: 'YUYV' (YUYV 4:2:2)
                Size: Discrete 1280x800
                        Interval: Discrete 0.100s (10.000 fps)
                Size: Discrete 1280x720
                        Interval: Discrete 0.100s (10.000 fps)

pi@RightPi:~$ sudo v4l2-ctl -d /dev/video0 --list-formats-ext
ioctl: VIDIOC_ENUM_FMT
        Type: Video Capture

        [0]: 'MJPG' (Motion-JPEG, compressed)
                Size: Discrete 1280x800
                        Interval: Discrete 0.008s (120.000 fps)
                        Interval: Discrete 0.010s (100.000 fps)
                Size: Discrete 1280x720
                        Interval: Discrete 0.008s (120.000 fps)
                Size: Discrete 800x600
                        Interval: Discrete 0.008s (120.000 fps)
                        Interval: Discrete 0.010s (100.000 fps)
                Size: Discrete 640x480
                        Interval: Discrete 0.008s (120.000 fps)
                        Interval: Discrete 0.010s (100.000 fps)
                Size: Discrete 320x240
                        Interval: Discrete 0.008s (120.000 fps)
                        Interval: Discrete 0.010s (100.000 fps)
        [1]: 'YUYV' (YUYV 4:2:2)
                Size: Discrete 1280x800
                        Interval: Discrete 0.100s (10.000 fps)
                Size: Discrete 1280x720
                        Interval: Discrete 0.100s (10.000 fps)


recorded: akit_26-11-03_23-38-42-bundle
notes: baseline is on threads 8 (not 4)

recorded: akit_26-11-03_23-58-01-bundle
notes: dec set to 2
logbench tried to download file which was 5.8mb and it is now still downloading 6min later at 44mb. usually it takes ~2min and about double the estimate (est doesn't include recorder images). look into this strange behavior where it never seemed to stop downloading! log: logbench-20261103-185848-727296.log
this was with the laptop connected via ethernet to the access point which connects to the robot via wifi. usually downloads around 700kb/s

i then connect via ethernet which is roughtly 5x faster (4mb/s) and it works. never seen it fail before like this over access point.


recorded: akit_26-11-04_00-18-32-bundle