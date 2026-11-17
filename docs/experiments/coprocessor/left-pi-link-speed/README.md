---
id: COP-left-pi-link-speed
title: Why does the Left Pi's Ethernet link run at 100 Mbit/s when the Right Pi's runs at 1000?
area: coprocessor
date: 2026-11-17
status: planned               # planned | running | analyzed | decided
decision: pending
robot_code: none (hardware; the Pi publisher already logs the link speed)
logs: the Pi publisher's NetSpeedMbps in any robot log, plus `python -m exprunner link`
analysis: none needed: read the speed after each step
raw_notes: fill in the table below as you go
---

# Left Pi link speed: 100 vs 1000 Mbit/s

## In short

Both Orange Pis are the same model on the same robot, but the Left Pi's Ethernet link comes up at **100 Mbit/s** and the Right Pi's
at **1000**. The logs from 11-07, 11-10 and 11-14 all show it, with no errors, drops or link flaps, so it is a steady slower link,
not a flaky one. It didn't change the vision results per second, but a 10x slower link slows everything else that crosses it: pulling
camera recordings and logs off the Pi, the PhotonVision stream, and any burst of traffic. It's a symptom of something physical that
should be found, because the same fault could get worse.

The test is a handful of swaps, each changing **one** thing, with the link speed read after each. Each swap says which of the
four possible causes it rules in or out. About 30 minutes.

## What we know

| Log | Left Pi | Right Pi | Errors / drops | Carrier changes (link flaps) |
|---|---|---|---|---|
| 11-07 (`akit_26-11-07_19-23-31`) | 100 | 1000 | 0 / 0 | 1 / 1 |
| 11-10 (`akit_26-11-10_23-43-08`) | 100 | 1000 | 0 / 0 | 1 / 1 |
| 11-14 (`akit_26-11-14_18-40-44`) | 100 | 1000 | 0 / 0 | 1 / 1 |

(Read from `RealOutputs/OrangePi/<Pi>/NetSpeedMbps`, `NetRxErrors`, `NetRxDropped`, `NetCarrierChanges`.)

## How a link picks its speed

When you plug in a cable, **both ends say which speeds they can do** and they use the best one they have in common. Gigabit
(1000) needs **all four wire pairs** in the cable to work; 100 Mbit needs only **two**. That is why the usual cause of "stuck at 100"
is not the Cat number but a cable or connector where one or two pairs aren't making contact.

## The four things it can be

1. **The cable or its connectors** (the most likely). A bad crimp, a bent or recessed pin, a cut or kinked cable, a flat or
   telephone-style cable with only two pairs, a coupler or wall-plate joiner in the middle. Cat5e or better is fine for gigabit;
   old Cat5 usually still works; the category matters far less than whether all eight wires are connected.
2. **The port or device at the other end.** A switch, radio port or adapter that only does 10/100, or a port set to 100.
3. **Something in between: a PoE injector or splitter, a coupler or an adapter.** Many cheap ones are 10/100 only.
4. **The Pi itself:** its Ethernet jack or chip, or its setting (a speed forced to 100 at some point, so it stopped offering 1000).

## The tool

From `tools/exprunner` (it uses the team SSH key the bootstrap installs; the Pis must be on the network):

```bash
python -m exprunner link
```

For each Pi it prints the link state, speed, duplex, how many times the link has dropped, and any errors, and then **what each end
of the cable offers**:

```text
LeftPi (LeftPi.local):
  end1: up, 100 Mbit/s, full duplex, 1 carrier change(s)
    this Pi advertises up to 1000; the other end up to 100 Mbit/s
    -> the OTHER END offers at most 100 Mbit/s: its port, or the device behind it, is the limit ...
```

That last line often settles it:

| It says | It means | Next |
|---|---|---|
| "the other end offers at most 100" | The port, or a device behind it (PoE splitter, adapter), only does 100 | Tests 2 and 3 below |
| "both ends advertise 1000 but the link is at 100" | They could both do gigabit, so the cable or a connector can't carry all four pairs | Test 1 |
| "this Pi's port is not advertising 1000" | The Pi was set to a lower speed | Test 4 |
| nothing, or "ethtool gave no advertised modes" | `ethtool` isn't on the Pi (`sudo apt install ethtool`, needs internet) | Do tests 1-3 and read the speed with the numbers from the logs |

The speed also shows in the robot log (`NetSpeedMbps`) after the next robot start, and live in LogBench's Health Check.

## Before you start: write down the setup

Look at the Left Pi's whole path and fill this in. It decides which tests make sense.

- [ ] **Cable:** the category printed on the jacket (`CAT5e`, `CAT6`, ...), its length, and any damage, kink or a connector
      with a bent or missing pin or a cracked latch.
- [ ] **Both ends:** what the other end plugs into (radio port number? a switch?), and how the Right Pi's cable does it.
- [ ] **Anything in between:** a PoE injector or splitter, a coupler, an adapter. Photograph it; read its label ("10/100" or "1000").
- [ ] **How the Pi is powered:** over the Ethernet cable (PoE) or a separate power supply. If over the cable, that **splitter or
      injector** is the first suspect.
- [ ] Run `python -m exprunner link` and paste the output for both Pis here.

## The tests

Change **one thing at a time**, read the speed after each (`python -m exprunner link --board LeftPi`; wait a few seconds after
re-plugging), and put the cable back before the next test. Write each result in the table.

| # | Change | If the Left Pi goes to 1000 | If it stays at 100 |
|---|---|---|---|
| 1 | **Replace the Left Pi's cable** with a short, known-good Cat6 (a new one, or the Right Pi's, moved there). Same ports | **The cable** (or a connector on it). Replace it, and check the other cables of that batch | Not the cable. Go to 2 |
| 2 | **Move the far end of the Left Pi's cable to a different, known-good gigabit port** (the port the Right Pi uses, with the Right Pi unplugged for the test) | **The port or device** it was on | Not the port. Go to 3 |
| 3 | **Take out everything in between**: plug the Left Pi **directly into the laptop's gigabit Ethernet** with the known-good cable (Windows: Settings, Network, Ethernet: the link speed shows 1000 when it works) | The Pi is fine; the fault is in the robot-side path (a splitter or injector, or the ports). Put the pieces back one at a time | **The Pi's own jack, or its setting.** Go to 4 |
| 4 | **Check the Pi's setting.** The `link` line "this Pi advertises up to" should say 1000. If it doesn't: `sudo ethtool -s end1 autoneg on`, and look for a speed forced in NetworkManager (`nmcli connection show` then `nmcli connection show <name> \| grep -i ethernet`) | A forced setting. Clear it and make it persistent | Likely hardware: swap the Pi with the Right Pi's position and see if the 100 follows the Pi |

If two tests could explain it (for example a bad cable *and* a 100 port), fix the first, then read the speed again: the other
will show next.

## Results (fill in)

| Test | What was changed | Left Pi speed | Right Pi speed | Notes |
|---|---|---|---|---|
| Before | nothing | 100 | 1000 | |
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |

**Cause found:** _(cable / port / splitter / Pi setting / Pi hardware)_  **Fix:** _..._

## Done when

- [ ] The Left Pi reports **1000** in `python -m exprunner link` and in the next robot log (`NetSpeedMbps`).
- [ ] No errors, drops or extra link changes (`carrier changes` stays at 1 per boot) after a full session of driving.
- [ ] Optional, to prove the speed is real: `iperf3` between the laptop and the Pi should show about 900+ Mbit/s on a gigabit link
      and about 94 on a 100 Mbit link (needs `sudo apt install iperf3` on the Pi, which needs internet; see
      [Pi internet access](../../../coprocessor/orangepi-internet-access.md)).
- [ ] Fill in the cause here, and add the fix to the robot's wiring notes so the next Pi swap keeps it.

## Next experiment

None needed if it's fixed. If the cause turns out to be the radio or a switch, check every other device on it too.
