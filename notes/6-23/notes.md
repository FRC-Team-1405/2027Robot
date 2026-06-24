# Camera Calibration test #1
used predefined positions on the ground. first row was 3ft from the wall second row was 6ft. each tag is 3ft away from the next in all directions.

## Positions:
```
   TAG

6   1   2

5   4   3
```

## Raw

| Position | L | R |
| - | - | - |
| 1 | 23 5/8 | 25 1/8 |
| 2 | 28 1/8 | 19 |
| 3 | 63 1/4 | 57 7/8 |
| 4 | 56 1/2 | 56 3/4 |
| 5 | 51 5/8 | 57 |
| 6 | 20 3/4 | 31 5/8 |


## Decimals

| Position | L | R |
| - | - | - |
| 1 | 23.625 | 25.125 |
| 2 | 28.125 | 19 |
| 3 | 63.25 | 57.875 |
| 4 | 56.5 | 56.75 |
| 5 | 51.625 | 57 |
| 6 | 20.75 | 31.625 |

# Camera Calibration Test #2

drove to any location and measured against the wall and the centerline. much easier i think.

| Position | To Wall | To Centerline | L | R |
| - | - | - | - | - |
| 1 | 27 | 10.5 | 31.5 | 22.5 |
| 2 | 48 | 8 | 50.25 | 45.5 |
| 3 | 56 | 14.5 | 51.5 | 60.5 |
| 4 | 33 | 14.5 | 26.5 | 39 |


Robot dimensions: 27x27in
Tag center height: 41.125in


# Radio stuff

what i tried:
Your Orange Pi is currently configured with a static FRC IP address (10.14.5.202) on its ethernet interface (end1). Because it has a static network configuration, it does not have a gateway or DNS settings pointing to your home router, which is why it cannot reach the internet through Aux 2.
To temporarily give it internet access to update packages, you need to change its configuration to DHCP.
## Step 1: Switch to DHCP
PhotonVision images are typically built on Debian/Ubuntu and use NetworkManager. Run the following commands to tell the ethernet port to request an IP address automatically from your home router:

sudo nmcli connection modify end1 ipv4.method auto
sudo nmcli connection up end1

(Note: If end1 is not the exact connection name in NetworkManager, find the correct name by running sudo nmcli connection show first).
## Step 2: Verify the Connection
Run ifconfig again. Your IP address should no longer be 10.14.5.202. Instead, it will look like your home network range (e.g., 192.168.1.X).
Test your internet connection using these two commands:

ping -c 3 8.8.8.8
ping -c 3 google.com

If the first one works but the second fails, your DNS is broken. Temporarily fix it by running:

echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf

## Step 3: Update and Upgrade
Now that you have internet access, run your updates:

sudo apt update && sudo apt upgrade -y

## Step 4: Revert to static FRC IP (Crucial)
Once your updates are finished, you must change the Orange Pi back to its static IP configuration. If you do not, the RoboRIO will not be able to find the PhotonVision camera stream when you unplug from your home network and go back to the robot.
Run these commands to restore your exact static setup:

sudo nmcli connection modify end1 ipv4.method manual ipv4.addresses 10.14.5.202/24
sudo nmcli connection up end1

If you encounter an error running the nmcli commands, please let me know:

* What error message does the terminal output?
* What is the output of running sudo nmcli connection show?


