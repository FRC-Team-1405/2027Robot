# Orange Pi 5 Reconfiguration Attempt — 2026-07-26

## Goal

User connected the control laptop (`piclaw`, a Raspberry Pi running Debian 13
"trixie", aarch64) directly via Ethernet to the team's Orange Pi 5, which
previously ran PhotonVision (hostname `photonvision.local`, last seen at
`10.14.5.202` via the robot radio's DHCP — see `notes/6-20/photonVisionSSH.txt`
and `docs/orangepi-internet-access.md`). Goal: do a complete refresh —
OS package updates, confirm/reinstall PhotonVision, confirm the Arducam is
detected, re-verify the `orangepi-nt-publisher` service — starting from
"may or may not still have PhotonVision running, likely needs a full update."

## Result: blocked at the network layer before ever reaching the Pi

I was not able to establish IP connectivity to the Orange Pi in this session.
Everything below is diagnostic groundwork so the next session (or the user,
at a real terminal with real `sudo`) can pick this up quickly.

## What was checked

- `ip addr` / `ip route` on `piclaw`: `eth0` is up at the link layer
  (`LOWER_UP`, carrier on) but has **no IPv4 address** — only an
  auto-assigned IPv6 link-local address.
- `nmcli device status`: `eth0` sits in `connecting (getting IP configuration)`
  indefinitely.
- `journalctl -u NetworkManager`: repeated DHCPv4 timeouts on `eth0`
  (`state changed no lease`, `ip-config-unavailable`) — no DHCP server is
  answering on the link.
- `dmesg`: the NIC is `smsc95xx` (the LAN9514 USB-Ethernet/hub chip built
  into this Pi's onboard Ethernet port — not a loose external dongle). The
  kernel log shows genuine PHY-level flapping:
  ```
  eth0: Link is Down
  eth0: Link is Up - 100Mbps/Full - flow control off
  ```
  repeating on a very regular ~21-22 second cycle, with no USB
  re-enumeration events around it. The regularity (not random) points away
  from a bad cable/connector and toward **the Orange Pi's own network stack
  cycling its interface between failed DHCP attempts** — i.e., both ends of
  this direct cable are DHCP *clients* waiting for a server that isn't
  there. This matches expectations: on the robot, the radio is the DHCP
  server for both the roboRIO and the Orange Pi; plugged directly into a
  laptop/Pi, neither side offers DHCP, so neither gets an address.
- IPv6 multicast discovery: `ping -6 -I eth0 ff02::1%eth0` only got a reply
  from `piclaw` itself — no other host answered on the segment. No
  `avahi-browse`/`avahi-resolve`/`nmap`/`arp-scan` tools are installed on
  `piclaw` to attempt further passive discovery.
- `tailscale status`: the Orange Pi is not on the team's tailnet — not a
  viable fallback path.

## The actual blocker: this session has no root

Fixing the above requires either (a) assigning a static IP to `eth0`, or
(b) running a temporary DHCP server on `eth0` so the Orange Pi can get a
lease the normal way — both require root. In this agent session:

```
$ sudo -n true
sudo: The "no new privileges" flag is set, which prevents sudo from running as root.
$ ip addr add 10.14.5.50/24 dev eth0
RTNETLINK answers: Operation not permitted
```

`sudo` is hard-blocked by a `no_new_privs` restriction on this shell (the
user `pi` is in the `sudo` group, so this is an environment/session
restriction, not a permissions problem with the account). **This is a wall
I can't script around** — it needs the user at a real terminal on `piclaw`
(or SSH'd in from elsewhere, e.g. `ssh pi@piclaw.local`) with normal `sudo`.

## Recommended next step (for the user to run on `piclaw` with real sudo)

Simplest robust fix — turn `piclaw` into a temporary DHCP server on `eth0`
so the Orange Pi can get an address the same way it would from the robot
radio:

```bash
sudo apt install -y dnsmasq
# Give piclaw's eth0 a static address in the old subnet, then serve DHCP on it:
sudo ip addr add 10.14.5.1/24 dev eth0
sudo dnsmasq --interface=eth0 --bind-interfaces \
  --dhcp-range=10.14.5.100,10.14.5.200,12h --no-daemon
```

Leave the `dnsmasq --no-daemon` running in a terminal and watch its output —
within ~30s it should log a `DHCPDISCOVER`/`DHCPACK` for the Orange Pi's
MAC, confirming it's alive and telling you its new IP. Then:

```bash
ssh pi@<leased-ip>          # or ssh pi@photonvision.local if mDNS resolves
```

Alternative/faster diagnostic if you just want to confirm the Pi is alive
before committing to the dnsmasq setup:

```bash
sudo tcpdump -i eth0 -n
```

If the Orange Pi is powered and cycling DHCP attempts, you'll see periodic
broadcast `DHCPDISCOVER` packets from its MAC address even with no server
running — confirming it's alive and exactly what it's waiting for.

## Once connectivity is restored — remaining "complete configuration" checklist

Not yet attempted (blocked on the above). In priority order, referencing
existing repo docs:

1. SSH in, check what's actually installed/running:
   ```bash
   sudo systemctl status photonvision.service
   photonvision version   # or check the jar under /opt/photonvision
   cat /etc/os-release
   ```
2. `sudo apt update && sudo apt upgrade -y` — the last SSH session
   (`notes/6-20/photonVisionSSH.txt`) shows this Pi has **no internet
   route at all**, so this will fail with DNS errors until
   `docs/orangepi-internet-access.md` (onboard Wi-Fi, temporary) is
   followed first. Don't forget the "disconnect Wi-Fi before it goes back
   on the robot" step in that doc — FRC field rules prohibit an active,
   unauthorized radio.
3. Check current PhotonVision version against the latest release; update
   if the coprocessor-research doc's finding is right that this board's
   software is stale.
4. Verify the Arducam is detected: `v4l2-ctl --list-devices` (or check
   PhotonVision's web UI camera list at `http://<ip>:5800`).
5. Re-verify/reinstall the `orangepi-nt-publisher` service per
   `docs/orangepi-nt-publisher-setup.md` (this was left mid-install per
   `notes/6-20/photonVisionSSH.txt` — `ntcore` module was never
   successfully installed, service was crash-looping).
6. Confirm Wi-Fi (`ap6275p-bluetooth.service`) is off/unassociated before
   trusting the Pi back on the robot.

## Files referenced

- `docs/orangepi-internet-access.md` — how to get the Pi temporary internet
- `docs/orangepi-nt-publisher-setup.md` — metrics publisher install steps
- `docs/coprocessor-research.md` — Orange Pi 5 vs Rubik Pi 3 status/context
- `notes/6-20/photonVisionSSH.txt` — prior SSH session log, same symptoms
  (no internet, `pip`/`ntcore` missing)
