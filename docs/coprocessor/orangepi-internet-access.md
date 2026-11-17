# Giving an Orange Pi internet from a laptop

The Pis only need the internet for **installing**: `apt` packages, the Python packages in the NetworkTables publisher's virtual
environment, and PhotonVision updates. Running them (publisher, recorder, PhotonVision) needs only the robot network.

> **Use the bootstrap first.** `coprocessor/Bootstrap-OrangePi.ps1` finds the Pi, installs the team SSH key, checks the Pi's internet,
> copies the scripts and runs the installer. The one part it can't do for you is the Windows **Internet Connection Sharing** switch
> below, and it stops with exact instructions when it needs it. See [coprocessor/README.md](../../coprocessor/README.md).

## What you need

- A USB-to-Ethernet adapter on the laptop, connected **directly** to the Pi's Ethernet port.
- The laptop on Wi-Fi with internet.
- The SSH account is **`pi`**. The team key is `coprocessor/ssh/id_ed25519_orangepi` (the bootstrap copies it to
  `~\.ssh\id_ed25519_orangepi`), so no password is needed. The Pis are `LeftPi.local` and `RightPi.local` on the robot network
  (names and cameras come from `coprocessor/robots.json`).

## Step 1: turn on sharing for the laptop's Wi-Fi adapter

1. Start menu, run `ncpa.cpl`.
2. Right-click the **Wi-Fi** adapter, Properties, **Sharing** tab, tick *Allow other network users to connect through this computer's
   Internet connection*. If it was already ticked, untick it, apply, then tick it again.

The laptop's Ethernet side becomes `192.168.137.1`, and the Pi gets an address on `192.168.137.x` from it.

## Step 2: connect

The bootstrap does this itself. By hand, if you need to:

```powershell
ssh -i $HOME\.ssh\id_ed25519_orangepi pi@LeftPi.local
```

If the name doesn't resolve while the Pi is on the shared connection, find its address (the number below is only an example; the
address is handed out dynamically and changes):

```powershell
arp -d *
arp -a | Select-String "192.168.137"
```

```text
Interface: 192.168.137.1 --- 0x8
  192.168.137.190       d2-45-38-09-f5-44     dynamic
```

```powershell
ssh -i $HOME\.ssh\id_ed25519_orangepi pi@192.168.137.190
```

## Last step: turn sharing off

Back in `ncpa.cpl`, Wi-Fi, Properties, Sharing: untick *Allow other network users...*. Then reconnect to the robot the usual way.
