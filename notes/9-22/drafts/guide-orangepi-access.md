# Guide: SSH into the Orange Pi (PhotonVision coprocessor)

> Draft distilled from notes 6-20, 6-23, 7-7, 7-26, 9-12. Suggested home:
> `docs/guides/orangepi-ssh-and-bench-access.md`, replacing `docs/orangepi-internet-access.md`.

## Quick reference

| | |
|---|---|
| Hostname | `photonvision.local` |
| Web UI | `http://photonvision.local:5800` |
| SSH user / password | `photon` / `vision` (PhotonVision image default, current image). The **old** image used `pi`. |
| Address on the robot | DHCP from the radio, `10.14.5.x`. The old image was static at `10.14.5.202`. |
| Board | Orange Pi 5, Ubuntu 24.04 (Rockchip, aarch64), Ethernet interface `end1` |
| Our services | `photonvision`, `orangepi-nt-publisher` (metrics), `orangepi-vision-recorder@left` / `@right` |
| roboRIO (for comparison) | `ssh lvuser@roborio-1405-frc.local`; logs are in `/home/lvuser/logs` |

## 1. On the robot network (normal case)

Connect the laptop to the robot radio, over Wi-Fi or Ethernet, then run:

```bash
ssh photon@photonvision.local
```

If `.local` doesn't resolve, get the IP from the PhotonVision UI or the radio's DHCP list.

## 2. Direct cable from a Windows laptop, with internet sharing

Use this when the Pi needs `apt` or `pip` and isn't on the robot. Worked on 7/7.

1. Plug a USB-Ethernet adapter on the laptop **directly** into the Pi.
2. Run `ncpa.cpl`, right-click your **Wi-Fi** adapter, open **Properties → Sharing**, and tick
   **Allow other network users to connect…**. If it's already ticked, untick it, apply, and tick it again.
3. Find the Pi's address. It will be on `192.168.137.x`. Run these in an admin PowerShell:
   ```powershell
   arp -d *
   arp -a | Select-String "192.168.137"
   ```
4. Connect with `ssh photon@192.168.137.<n>`.
5. When you're done, untick the sharing box. Otherwise the laptop won't talk to the robot normally.

## 3. Direct cable from a Linux box (for example `piclaw`), with DHCP and NAT

This worked on 7/26. The Linux box gives the Pi an address and routes it to the internet. The Pi's
own Wi-Fi is never turned on, so there's nothing to switch off before competition.

```bash
# on the Linux box
sudo apt install -y dnsmasq
sudo nmcli connection modify "Wired connection 1" ipv4.method manual \
  ipv4.addresses 10.14.5.1/24 ipv4.never-default yes ipv6.method ignore
sudo nmcli connection up "Wired connection 1"
```

`/etc/dnsmasq.d/eth0-dhcp.conf`:
```
interface=eth0
bind-interfaces
except-interface=lo
dhcp-range=10.14.5.100,10.14.5.200,12h
dhcp-authoritative
port=0
dhcp-option=3,10.14.5.1
dhcp-option=6,8.8.8.8,1.1.1.1
```

```bash
sudo systemctl restart dnsmasq
sudo sysctl -w net.ipv4.ip_forward=1
sudo iptables -t nat -A POSTROUTING -s 10.14.5.0/24 -o wlan0 -j MASQUERADE
cat /var/lib/misc/dnsmasq.leases     # shows the Pi's leased IP
```

The iptables and sysctl changes don't survive a reboot of the Linux box. Run them again if it restarts.

## Once you're in

```bash
systemctl status photonvision orangepi-nt-publisher
journalctl -u orangepi-nt-publisher -f      # follow a service's log
v4l2-ctl --list-devices                     # cameras show up as generic UVC ("Cam1"), which is normal
nmcli connection show; ip addr              # networking
sudo ping -c 3 8.8.8.8                      # ping needs sudo on this image
```

Copy vision recordings to the laptop. Run this from the repo root on the laptop:
```bash
scp -r photon@photonvision.local:/home/photon/vision-recordings/left/<session> ./recordings/
```
The logbench **Fetch bundle** page does this for you, together with the matching rio log.

## Gotchas we've hit

- **Power.** The Orange Pi 5 needs 5 V at 3–4 A over **USB-C PD**. A USB-A brick with a USB-A→C
  adapter made the Ethernet link drop and come back every ~21 s, and nothing appeared in the logs.
  A link that flaps on a regular timer points to power; a bad cable flaps at random.
- **No internet means `apt update` fails with "Temporary failure resolving".** The Pi has no
  route off the robot network. Use method 2 or 3 above.
- **Clock far behind after a fresh flash.** One flash booted ~641 days behind, and `apt` failed
  with "Release file … not valid yet". It fixes itself within a minute of getting internet; rerun `apt update`.
- **Non-interactive `apt upgrade`.** PhotonVision modifies `/etc/issue`, so dpkg stops to ask about
  it. Use:
  `sudo apt-get upgrade -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"`
- **SSH drops during an upgrade of `openssh-server`.** The upgrade keeps running on the Pi. Wait a
  few minutes and reconnect. Don't start a second `apt`; it will fail on the dpkg lock.
- **Python packages.** The ntcore package on PyPI is `pyntcore`; `robotpy-ntcore` returns a 404.
  Install it in a venv (`/home/photon/.venv-ntpublisher`). Older images don't ship `pip`.
- **If you turn on the Pi's own Wi-Fi, turn it off before the Pi goes back on the robot.** FRC
  doesn't allow unauthorized radios on the field.
