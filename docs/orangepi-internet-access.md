# Giving the Orange Pi Internet Access (Without Losing Laptop Access)

**Context:** Installing the `orangepi-nt-publisher` service requires `pip install robotpy-ntcore` (and `python3-pip` itself, on some images). The Orange Pi has no internet route by default — see `notes/6-20/photonVisionSSH.txt` for the failed install attempt (`apt update` and `pip` both fail with DNS resolution errors).

## Current topology

```
Laptop ──Ethernet──► Robot Radio ──Ethernet──► Orange Pi (+ roboRIO)
```

The laptop reaches the Pi over the closed robot network via the radio (`pi@photonvision.local`, currently `10.14.5.202`). Any fix needs to leave that path working.

## Recommendation: use the Orange Pi's onboard Wi-Fi

The SSH log shows `ap6275p-bluetooth.service` in `/etc/systemd/system/` — this is the AP6275P Wi-Fi/Bluetooth combo chip built into the Orange Pi 5 board. **The Pi can get its own internet connection over Wi-Fi without touching the Ethernet/radio link at all.** This is the cleanest option: zero risk to the existing laptop↔radio↔Pi path, no DHCP conflicts, no rewiring.

### Steps

1. SSH in as usual (`ssh pi@photonvision.local`, over the existing Ethernet/radio path).
2. Check NetworkManager is available (Ubuntu 24.04 images normally ship with it):
   ```bash
   nmcli -v
   ```
3. Connect to any Wi-Fi network with internet (phone hotspot, shop Wi-Fi, home Wi-Fi):
   ```bash
   sudo nmcli device wifi list
   sudo nmcli device wifi connect "<SSID>" password "<password>"
   ```
4. Verify the Pi has internet *in addition to* the existing Ethernet link:
   ```bash
   ping -c 3 8.8.8.8
   sudo apt update
   ```
   The `ports.ubuntu.com` / `ppa.launchpad.net` DNS errors from the log should be gone.
5. Do the install work (see `docs/orangepi-nt-publisher-setup.md`).
6. **Before the Pi ever goes on a robot/field again, disconnect or forget the Wi-Fi network.** FRC robots may not have unauthorized active wireless communication on the field (game manual robot rules, e.g. R704-class rules) — the AP6275P radio must be off or unassociated during any match. The simplest way to guarantee this is to forget the network after you're done:
   ```bash
   sudo nmcli connection delete "<SSID>"
   sudo systemctl disable --now wpa_supplicant   # if NetworkManager doesn't already manage this
   ```
   Confirm with `nmcli device status` that the Wi-Fi device shows `disconnected`.

## Alternative: Windows Internet Connection Sharing (ICS)

You can share your laptop's Wi-Fi internet over the same Ethernet adapter that's plugged into the radio. Windows will NAT/DHCP that adapter, and anything downstream on the radio's switch (the Pi, the roboRIO) can reach the internet through your laptop.

**Caveat — DHCP conflict risk:** ICS turns the laptop's Ethernet adapter into a DHCP server (`192.168.137.1/24` by default). If the robot radio is also running its own DHCP server on that LAN (common in OpenMesh/Vivid-Hosting "practice" mode), you now have two DHCP servers on one switched network, which causes intermittent IP conflicts for anything plugged into the radio — including the roboRIO. Only do this if you're sure nothing else on the radio's network depends on a stable DHCP lease during the session, and revert it immediately afterward.

Steps:
1. Settings → Network & Internet → confirm you have a working Wi-Fi (or other) internet connection.
2. Control Panel → Network and Sharing Center → click your internet-connected adapter → Properties → **Sharing** tab → check "Allow other network users to connect through this computer's Internet connection" → select the Ethernet adapter connected to the radio.
3. The Pi should pick up a `192.168.137.x` address (it may need `sudo dhclient` or a reboot of its network interface to grab the new lease — its address will change from `10.14.5.202`, so re-resolve `photonvision.local` or check the new IP via the radio).
4. Run `sudo apt update` / `pip install` on the Pi as normal.
5. Turn ICS back off (uncheck the Sharing box) and confirm the radio/roboRIO/Pi network returns to its normal `10.14.x.x` addressing before you trust it for robot use again.

This works, but the Wi-Fi option above is preferred because it doesn't touch the robot's network addressing at all.

## Alternative: feed internet into the radio's WAN/uplink port

Plugging an internet-connected Ethernet cable into the robot radio's WAN/PoE-in port is plausible in theory (some teams do this at home to give the whole robot network internet access), but:
- It only works if the radio is configured in a bridging mode that actually routes the WAN port to the LAN ports — by default FRC radios are configured for the FMS network topology, not as general-purpose internet routers, and the practice/home configuration varies by radio model and firmware.
- It risks accidentally changing the radio's configuration away from its competition-ready state.

**Not recommended** as the default approach — only use it if you specifically need the *roboRIO* (not just the Pi) to have internet too, and you're comfortable re-verifying the radio's competition configuration afterward.

## Alternative: offline package transfer (no internet on the Pi at all)

If Wi-Fi isn't available and you don't want to touch ICS/the radio, you can download the needed files on the laptop (which has internet) and copy them to the Pi over the existing SSH/Ethernet link — no change to the Pi's network needed.

1. On the laptop (or any machine with internet and Python), download wheels matching the Pi's platform (Ubuntu 24.04, `aarch64`, Python 3.12):
   ```bash
   pip download --no-deps --platform manylinux_2_28_aarch64 --python-version 312 --implementation cp --abi cp312 -d wheels robotpy-ntcore pip
   ```
   Note: confirm `robotpy-ntcore` actually publishes `manylinux_aarch64` wheels for cp312 on PyPI before relying on this — if not, you'll need to build from source on a matching ARM64 Ubuntu 24.04 system (e.g. a Raspberry Pi, or a cloud ARM64 VM) instead of cross-downloading.
2. Copy the `wheels/` folder to the Pi:
   ```bash
   scp -r wheels pi@photonvision.local:/home/pi/
   ```
3. On the Pi, install pip itself from the downloaded wheel, then install the rest offline:
   ```bash
   python3 /home/pi/wheels/pip-*.whl/pip install --no-index --find-links=/home/pi/wheels robotpy-ntcore
   ```

This is the most fiddly option and should be the fallback, not the default — only use it if Wi-Fi truly isn't an option (e.g. competition venue with locked-down guest networks).

## Decision summary

| Option | Risk to existing laptop↔Pi access | Setup effort | Recommended |
|---|---|---|---|
| Pi's onboard Wi-Fi | None | Low | **Yes — default choice** |
| Windows ICS | Possible DHCP conflict on radio's LAN | Low | Only if Wi-Fi unavailable |
| Internet into radio's WAN port | Could disturb radio's comp config | Medium | Avoid unless roboRIO also needs internet |
| Offline wheel transfer via scp | None | High | Fallback when no Wi-Fi exists anywhere |
