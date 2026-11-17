for all these tests i set public static final boolean VISION_EXTENDED_NT_LOGGING = false;
hopefully that didn't mess up the results.


RealOutputs/RIO was under advantageKit in NT

2b photon vision still saves:
```
pi@leftpi:~$ journalctl -u photonvision --since "10 min ago" | grep -i locked
Hint: You are currently not seeing messages from other users and the system.
      Users in groups 'adm', 'systemd-journal' can see all messages.
      Pass -q to turn off this notice.
```

bootstrapped both pi's and switched to beta. i didn't do that until after akit_26-11-07_18-22-17-bundle

AS and Elastic open, LB closed: akit_26-11-07_19-03-35-bundle

AS and Elastic open, LB open (fetch bundle screen): akit_26-11-07_19-10-49-bundle

just driverstation: akit_26-11-07_19-13-10-bundle

# driverstation, AS, Elastic, LB all open for these tests, PV closed as always

R6 - dec 1 (enabled auto twice, once without setting the autonomous routine): akit_26-11-07_19-19-16-bundle

R13 - dec2, high res: akit_26-11-07_19-23-31-bundle