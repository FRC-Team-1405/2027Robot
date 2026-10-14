root@photonvision:/home/pi# ls vision-recordings/ -las
total 12
4 drwxr-xr-x 3 root root 4096 Jul 15 13:04 .
4 drwxr-x--- 7 pi   pi   4096 Jul 15 13:04 ..
4 drwxr-xr-x 2 root root 4096 Jul 15 13:04 20260715-130404
root@photonvision:/home/pi# ls vision-recordings/20260715-130404/ -las
total 476
 4 drwxr-xr-x 2 root root  4096 Jul 15 13:04 .
 4 drwxr-xr-x 3 root root  4096 Jul 15 13:04 ..
16 -rw-r--r-- 1 root root 15725 Jul 15 13:04 frame_6149.951068.jpg
16 -rw-r--r-- 1 root root 15549 Jul 15 13:04 frame_6150.184721.jpg
16 -rw-r--r-- 1 root root 15427 Jul 15 13:04 frame_6150.518309.jpg
16 -rw-r--r-- 1 root root 15605 Jul 15 13:04 frame_6150.851809.jpg
16 -rw-r--r-- 1 root root 15759 Jul 15 13:04 frame_6151.185302.jpg
16 -rw-r--r-- 1 root root 15571 Jul 15 13:04 frame_6151.518713.jpg
16 -rw-r--r-- 1 root root 15447 Jul 15 13:04 frame_6151.852148.jpg
16 -rw-r--r-- 1 root root 15491 Jul 15 13:04 frame_6152.185777.jpg
16 -rw-r--r-- 1 root root 15739 Jul 15 13:04 frame_6152.519094.jpg
16 -rw-r--r-- 1 root root 15851 Jul 15 13:04 frame_6152.852579.jpg
16 -rw-r--r-- 1 root root 15609 Jul 15 13:04 frame_6153.185960.jpg
16 -rw-r--r-- 1 root root 15465 Jul 15 13:04 frame_6153.519399.jpg
16 -rw-r--r-- 1 root root 15679 Jul 15 13:04 frame_6153.852915.jpg
16 -rw-r--r-- 1 root root 15839 Jul 15 13:04 frame_6154.186261.jpg
16 -rw-r--r-- 1 root root 15636 Jul 15 13:04 frame_6154.519690.jpg
16 -rw-r--r-- 1 root root 15398 Jul 15 13:04 frame_6154.853185.jpg
16 -rw-r--r-- 1 root root 15797 Jul 15 13:04 frame_6155.186583.jpg
16 -rw-r--r-- 1 root root 15704 Jul 15 13:04 frame_6155.519995.jpg
16 -rw-r--r-- 1 root root 15534 Jul 15 13:04 frame_6155.853579.jpg
16 -rw-r--r-- 1 root root 15445 Jul 15 13:04 frame_6156.186865.jpg
16 -rw-r--r-- 1 root root 15537 Jul 15 13:04 frame_6156.520467.jpg
16 -rw-r--r-- 1 root root 15731 Jul 15 13:04 frame_6156.853778.jpg
16 -rw-r--r-- 1 root root 15784 Jul 15 13:04 frame_6157.187264.jpg
16 -rw-r--r-- 1 root root 15560 Jul 15 13:04 frame_6157.520692.jpg
16 -rw-r--r-- 1 root root 15466 Jul 15 13:04 frame_6157.854256.jpg
16 -rw-r--r-- 1 root root 15444 Jul 15 13:04 frame_6158.187532.jpg
16 -rw-r--r-- 1 root root 15779 Jul 15 13:04 frame_6158.520984.jpg
16 -rw-r--r-- 1 root root 15845 Jul 15 13:04 frame_6158.854416.jpg
16 -rw-r--r-- 1 root root 15650 Jul 15 13:04 frame_6159.187851.jpg
 4 -rw-r--r-- 1 root root  1651 Jul 15 13:04 manifest.jsonl




its working. i downloaded a test autonomous (circle facing tag) log and the corresponding vision recordings.
`scp pi@photonvision.local:/home/pi/vision-recordings/20260715-133450/* .\notes\9-12\visionRecorder5\`

TODO: we should add a tab to the logbench that pulls up the robots logs (from the rio) and matches the vision recordings (from the pi) and puts them together with an easy download button so i can pull that from the robot after a match