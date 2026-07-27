# Orange Pi 5 Reconfiguration Attempt — 2026-07-26

## Update (same day, second pass with working sudo)

Sudo access was restored in-session. Did the planned fix:

1. `sudo apt-get install -y dnsmasq` — clean install, no pre-existing config
   to worry about.
2. Set `eth0` to a stable static IP via NetworkManager instead of a raw
   `ip addr add`, so NM's own DHCP retry loop wouldn't fight it or flush it:
   ```bash
   sudo nmcli connection modify "Wired connection 1" ipv4.method manual \
     ipv4.addresses 10.14.5.1/24 ipv4.never-default yes ipv6.method ignore
   sudo nmcli connection up "Wired connection 1"
   ```
3. Scoped dnsmasq to DHCP-only on `eth0` (DNS disabled via `port=0` so it
   doesn't touch the box's existing resolver setup, which depends on
   Tailscale's MagicDNS at `100.100.100.100`) — config installed at
   `/etc/dnsmasq.d/eth0-dhcp.conf`:
   ```
   interface=eth0
   bind-interfaces
   except-interface=lo
   except-interface=wlan0
   except-interface=tailscale0
   dhcp-range=10.14.5.100,10.14.5.200,12h
   dhcp-authoritative
   port=0
   ```
   `sudo systemctl restart dnsmasq` confirmed via `journalctl -u dnsmasq`:
   `DHCP, sockets bound exclusively to interface eth0`.

**Revised finding — this is very likely a physical-layer problem, not a
DHCP standoff.** After the DHCP server was live and ready, `eth0` kept
flapping `Link is Down` / `Link is Up - 100Mbps/Full` on the *exact same*
~21-22 second cadence as before any changes were made — the fix had zero
effect on the flap pattern, which it should have if the far end were a
DHCP client that just needed a server to answer it.

More telling: `sudo tcpdump -i eth0 -n -e` run twice (30s, then 25s) across
multiple full up/down cycles captured **zero incoming packets** — only
this box's own outgoing IPv6 multicast listener reports. No ARP, no DHCP
discover, no mDNS, nothing arriving from any remote device, ever. A live
DHCP client (dhclient/NetworkManager/systemd-networkd) retries every few
seconds and would have shown up well within that window if it were
actually there and trying.

**Conclusion:** something at the physical layer is producing successful
100Mbps/Full autonegotiation but no actual data is crossing the link in
either direction from a remote device. This is consistent with:
- a marginal/damaged Ethernet cable,
- a loose connector on one end,
- the Orange Pi's Ethernet port itself not actually connected/live, or
- the Orange Pi not being powered on at all.

This can't be diagnosed further from software — it needs eyes on the
hardware. **Recommended physical checks, in order:**
1. Confirm the Orange Pi has power (status LEDs lit / fan spinning).
2. Reseat the Ethernet cable fully on both ends (both this Pi's port and
   the Orange Pi's port) — listen/feel for the clip click.
3. Check the Orange Pi's own Ethernet port link LED — if it's dark or
   also flapping, that corroborates a cable/port problem rather than
   something specific to this box's NIC.
4. Swap in a known-good cable if one's available.
5. Once the cable/power is confirmed good, no further software changes
   should be needed on this end — the static IP + scoped DHCP server are
   already in place and listening, so a real link partner should get a
   lease within seconds. Watch with:
   ```bash
   sudo journalctl -u dnsmasq -f
   cat /var/lib/misc/dnsmasq.leases
   ```

The static-IP and dnsmasq changes above were left in place (harmless,
scoped only to `eth0`, doesn't touch DNS or other interfaces) so the next
session can pick up immediately once the cable/power issue is resolved.

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
