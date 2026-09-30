# Reference: coprocessor health and field rules

> Short facts that don't warrant their own doc. Suggested home: add them to
> `docs/robot_details/vision_specs.md` or `docs/coprocessor-research.md`.

## Orange Pi 5 thermals (7/14)
- It idles at **~73 °C** by our publisher's reading and **~77 °C** by PhotonVision's. Temperature
  barely changes whether a tag is in view or not, or whether the robot is enabled or idle.
- The CPU starts throttling at **85 °C**. Aim to stay **under 75 °C**, which means we're right at the
  edge now. **A fan is recommended.**
- The two readings differ by about 4 °C and probably come from different thermal zones. Check
  `/sys/class/thermal/thermal_zone*/type`.

## Power (7/26)
- The board needs 5 V at 3–4 A (15–20 W) over USB-C **PD**, with a real C-to-C cable. A USB-A
  source with an adapter causes brownouts. The symptom was the Ethernet link flapping every ~21 s,
  with no under-voltage message in dmesg; Rockchip boards don't log one.

## Radio bandwidth (7/21)
- Game manual rule **R704** (2026): traffic between the robot and the operator console is limited to
  **7.0 Mbit/s** on the Vivid Hosting radio and 4.0 Mbit/s on OpenMesh, on the allowed ports only.
  Camera streams to the dashboard count against this and are a likely cause of the camera delay we've seen.
  https://frctools.com/2026/rule/R704. Re-check this rule when the 2027 manual comes out.

## Open question: DS wiring (9/5)
The DS plugs into radio port **AUX 2** (not the DS port) through a PoE-splitter cable with the power
lead cut off. Check against the VH-109 port guide or with a CSA before relying on it at an event.
