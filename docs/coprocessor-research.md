# PhotonVision Coprocessor Research: Rubik Pi 3 vs Orange Pi 5

**Last updated:** 2026-06-07  
**Author:** Research compiled for FRC Team 1405, 2027 season planning

---

## Summary / Bottom Line

**Recommendation: Rubik Pi 3** (available from AndyMark, ~$110)

The Orange Pi 5 is functionally capable but is increasingly unavailable, overpriced, and being phased out of community recommendations. The Rubik Pi 3 is now the go-to coprocessor recommended by the PhotonVision development team and the broader FRC community for 2026/2027. For teams only doing AprilTag detection (no object detection), a Raspberry Pi 5 is a cost-effective and fully adequate alternative.

---

## The Sam948 Context (What He Said and Why)

**Sam Freund (Chief Delphi: @Sam948 / GitHub: @samfreund)** is a core PhotonVision developer who led Rubik Pi integration. He is one of the most authoritative voices on PhotonVision hardware choices.

### The Post You Were Looking For

**Thread:** "How important is USB3 to vision? And which co-processor do you recommend?"  
**Link:** https://www.chiefdelphi.com/t/how-important-is-usb3-to-vision-and-which-co-processor-do-you-recommend/509330/6  
**Date:** December 20, 2025  
**Sam948 Post #6 (exact quote):**

> "For apriltag detection, it typically does. The main advantage of the orange pi or rubik is the ability to run object detection."

This was in response to the question of whether USB3 matters and which coprocessor to buy after the **OPi5Max was discontinued**. Sam948's answer implies:
- A plain Raspberry Pi 5 is sufficient for AprilTag-only detection
- Orange Pi 5 / Rubik Pi 3 are both worth it **only if you want object detection**
- Between those two, the community consensus (and Sam's involvement) strongly favors the Rubik Pi 3

Sam948 also posted in the same thread (#10):

> "If you want to run uncompressed higher resolutions, [USB3] can very much matter. If you're only running lower resolutions, or you're okay with compression, then I'd agree that 3.0 vs 2.0 doesn't matter as much."

### Why the Community No Longer Recommends Orange Pi 5

From the same thread, community member **billbo911** (post #4, December 20, 2025):

> "For several years the Opi5 in its various configurations was THE GO TO board for vision... Now that the availability of the OPi-5 is driving prices into the ridiculous range, the Rubik Pi 3 comes along and sets a new standard for performance. It is on par with the Opi5 for AprilTag, but it has 3X the performance available for Object Detection. IMHO, for $110, it is by far the better option between the two."

**Context on availability:**
- The **OPi5 Max** — previously the most popular variant (2x USB3) — is **no longer available**
- The remaining OPi5 models (OPi5+, OPi5 Pro) have spiked in price
- Rubik Pi 3 is $110 at AndyMark with reliable US-based supply

---

## Rubik Pi 3 — Deep Dive

### Hardware Specs

| Spec | Value |
|------|-------|
| **SoC** | Qualcomm Dragonwing QCS6490 |
| **CPU** | 8-core |
| **NPU** | 12 Dense TOPS |
| **GPU** | Independent (dedicated) |
| **Storage** | Onboard fast UFS (no SD card needed) |
| **USB** | 2x USB 3.0 (per Qualcomm datasheet; AndyMark listing shows 1 — verify physically) |
| **Power** | 12V input required |
| **Price** | ~$110 (AndyMark Vision Bundle) |

**Source:** [AndyMark Vision Bundle](https://andymark.com/products/rubik-pi3-vision-bundle) | [Qualcomm QCS6490 datasheet](https://www.qualcomm.com/internet-of-things/products/q6-series/qcs6490)

### PhotonVision Support

- **Full native support** added in **PhotonVision v2026.1.1** (January 2026)
- Dedicated object detection via TensorflowLite + JNI bindings ([rubik_jni](https://github.com/PhotonVision/rubik_jni))
- Supports YOLOv8 and YOLOv11 models (640x640, `.tflite` format for QCS6490)
- Sam Freund personally authored the Rubik Pi integration PRs (#1989, #2005, #2110)
- PhotonVision 2026 ships with a pre-trained FUEL detection model for the 2026 game

**Source:** [PhotonVision v2026.1.1 release thread](https://www.chiefdelphi.com/t/photonvision-2026-releases-2026-3-4/512436) | [Rubik Pi Object Detection docs](https://docs.photonvision.org/en/latest/docs/objectDetection/rubik.html)

### Real-World Performance (FRC Teams)

**Team 1640 (Sab-BOT-age)** demonstrated at Ramp Riot offseason event:
- 3 cameras running simultaneously on one Rubik Pi 3
- 2 cameras: 3D AprilTag pipelines
- 1 camera: AI object detection pipeline
- ~45 FPS on all three at high resolution
- "Flawless" tag tracking and object detection

> "We are trying out the Rubik Pi and right now its running great with three cameras (about 60fps per camera on lowest resolution)... Team 1640 did a demo at a competition a bit ago which featured 2 cameras for april tag detection and 1 camera for object detection and the tag tracking and object detection were flawless running at 60fps per camera." — @JustinEdg, CD post #3 (Dec 20, 2025)

**Announcement thread:** [Introducing the RUBIK PI 3: AprilTag Processing + Object Detection!](https://www.chiefdelphi.com/t/introducing-the-rubik-pi-3-apriltag-processing-object-detection/507648)  
Beta testing teams: 1640, 1538, 3255, 614, 4499, 7127

### Power Requirements (Important!)

- **Requires 12V input** — different from Orange Pi (5V) and Raspberry Pi (5V)
- Recommended regulator: DROK Buck Boost Converter or Redux Robotics Zinc-V set to 12.1V
- Some teams found powering via 5V breakout pins to be unstable
- Power draw varies; size your regulator accordingly

**Source:** [CD post #14 by @Gdeaver](https://www.chiefdelphi.com/t/introducing-the-rubik-pi-3-apriltag-processing-object-detection/507648)

### Object Detection Model Format

- Supports: **YOLOv8 / YOLOv11** (640x640 `.tflite`, quantized, QCS6490 SOC format)
- Conversion notebook provided by PV: `scripts/rubik_conversion.ipynb` (Google Colab compatible)
- Edge Impulse YOLO-Pro models can be converted via [this notebook](https://github.com/ramalamadingdong/yolo-pro-to-yolo11/tree/main)
- Only quantized models are supported

---

## Orange Pi 5 — Current Status

### What Still Works

- Fully supported by PhotonVision for both AprilTag and object detection
- Object detection uses RKNN (RK3588/RK3588S NPU, ~4 TOPS)
- Supports up to 2 object detection streams + 2 AprilTag streams at 1280×800 30fps (per PV docs)
- Teams who already have one: **keep using it**, no reason to replace

### Why It's Being Phased Out of New Recommendations

| Issue | Detail |
|-------|--------|
| **OPi5Max discontinued** | The best variant (2x USB3) is no longer available |
| **Price inflation** | Remaining models have surged in price; no longer a clear value win |
| **NPU performance** | ~4 TOPS vs Rubik Pi's 12.5 TOPS — 3x disadvantage for object detection |
| **Power/tooling** | Rubik Pi has better Qualcomm tooling for custom model development |
| **Supply chain** | Sourced from China; lead times from Aliexpress/Amazon are inconsistent |
| **OPi6 is provisional** | PV v2026.3.1 added OPi6 image but "not recommended for general consumption at present" |

### Orange Pi 5 Variants Still Available

| Model | USB3 Ports | Notes |
|-------|-----------|-------|
| OPi5 (standard) | 1 | Most common, adequate for 1 USB3 camera |
| OPi5+ | 2 | Still available; has 2x USB3 |
| OPi5 Pro | 1 USB3 + 1 USB-C | Less common |
| OPi5 Max | 2 | **Discontinued / not available** |

---

## Raspberry Pi 5 — AprilTag-Only Alternative

If the goal is **only AprilTag detection** (no object detection), a **Raspberry Pi 5 (2GB)** is fully adequate per Sam948 and the PV docs.

| Spec | Raspberry Pi 5 |
|------|---------------|
| Official PV support | Yes |
| AprilTag streams | Up to 2 at 1280×800 30fps |
| Object detection | No NPU support |
| USB3 ports | 2 |
| Price | ~$50–60 |
| Supply | Reliable, wide distribution |

> "IMHO a plain old raspberry pi 5 works fine, has two USB3 ports, reasonably priced." — @truher, CD post #5 (Dec 20, 2025)

**Recommended by Sam948 for AprilTag-only use** (implied by his post #6 in the USB3 thread).

---

## Head-to-Head: Rubik Pi 3 vs Orange Pi 5

| Category | Rubik Pi 3 | Orange Pi 5 (4GB) |
|----------|-----------|-----------------|
| **Price** | ~$110 (AndyMark) | ~$80–120+ (inflated, varies) |
| **NPU TOPS** | 12.5 TOPS | ~4 TOPS (RKNN) |
| **Object detection** | Yes (YOLOv8/11 via TFLite) | Yes (RKNN) |
| **AprilTag perf** | On par with OPi5 | Established, proven |
| **Multi-camera** | 3 cams simultaneously (demo'd) | 2 obj + 2 AprilTag (PV docs) |
| **USB3 ports** | 2 (per datasheet) | 1–2 depending on variant |
| **Power input** | 12V | 5V |
| **Storage** | UFS (onboard, no SD card) | SD card (or M.2 SSD) |
| **PV support** | v2026.1.1+ (new, active) | Long-standing, well-tested |
| **US availability** | AndyMark, FIRST Choice | Amazon/Aliexpress (variable) |
| **Community track record** | Growing (1640, 1538, 3255, etc.) | Extensive (4+ years) |
| **Qualcomm tooling** | Yes (better custom model support) | No |
| **OPi recommendation** | PV team's current recommendation | Teams who already have one |

**AprilTag performance is essentially equal.** The Rubik Pi's major advantage is 3x NPU performance for object detection and better long-term supply/support.

---

## What PhotonVision Docs Currently Say

From [Common Hardware Setups](https://docs.photonvision.org/en/latest/docs/quick-start/common-setups.html) (as of 2026):

> **Orange Pi 5 4GB** — Supports up to 2 object detection streams, along with 2 AprilTag streams at 1280x800 (30fps).  
> **Raspberry Pi 5 2GB** — Supports up to 2 AprilTag streams at 1280x800 (30fps).
>
> Note: The Orange Pi 5 is the only currently supported device for object detection.

⚠️ **Note:** This page appears slightly out of date — the Rubik Pi 3 was added in v2026.1.1 and is fully supported. The docs navigation includes a dedicated "Rubik Pi 3 Object Detection" page. The common-setups note likely predates the Rubik Pi integration.

---

## Other Notable Alternatives

### Luma P1

- Smart camera (all-in-one, like Limelight) running PhotonVision
- Added in PV v2026.1.1
- More reliable for teams who struggled with coprocessor + cable setups
- Recommended by some teams as a Limelight migration path

**Thread:** [Introducing Luma P1, an affordable, high-performance AprilTag smart camera](https://www.chiefdelphi.com/t/introducing-luma-p1-an-affordable-high-performance-apriltag-smart-camera/506851)

### Custom FRC Board (Radxa CM5-based)

- Community effort to build a compact, FRC-hardened carrier board for the Radxa CM5
- Same RK3588 chipset as the OPi5 family — same PV object detection performance
- Smaller footprint, direct 12V power, no exposed SD card, locking USB-C camera port
- Target price: ~$159 total; not yet commercially available
- Sam948 engaged positively on this project

**Thread:** [Orange Pi alternative for photonvision hardware](https://www.chiefdelphi.com/t/orange-pi-alternative-for-photonvision-hardware/503918)

---

## Recommended Camera Pairings (from PV docs + community)

| Use Case | Camera | Notes |
|----------|--------|-------|
| AprilTag detection | Arducam OV9281 | Global shutter, USB2, wide use |
| Object detection | Arducam OV9782 | Color, global shutter |
| High-res AprilTag | ThriftyCam | USB3 recommended; 2MP |
| Driver camera | OV9281, OV9782, Pi Cam V1 | Any of the above |

**For ThriftyCam:** Use USB3 port on the Rubik Pi or OPi5+. USB3 matters at full resolution (60fps, uncompressed), but lower resolutions work fine over USB2.

---

## Team 1405 Recommendation

For the **2027 season**:

1. **New purchase: Rubik Pi 3** — better object detection, same AprilTag performance, US supply via AndyMark, actively supported by PV team. Budget 12V regulator (Zinc-V or DROK ~$20).
2. **If AprilTag-only:** Raspberry Pi 5 is cheaper and simpler.
3. **If we already have OPi5:** No need to replace; it works well, but don't buy more.
4. **Watch for:** Rubik Pi 3 in FIRST Choice (confirmed to be added) — may reduce cost.

---

## Sources

| Source | URL |
|--------|-----|
| Sam948 post on USB3/coprocessor (the main post) | https://www.chiefdelphi.com/t/how-important-is-usb3-to-vision-and-which-co-processor-do-you-recommend/509330/6 |
| Rubik Pi 3 Introduction thread | https://www.chiefdelphi.com/t/introducing-the-rubik-pi-3-apriltag-processing-object-detection/507648 |
| PhotonVision 2026 Release notes (v2026.1.1 + patches) | https://www.chiefdelphi.com/t/photonvision-2026-releases-2026-3-4/512436 |
| Sam948 post on v2026.3.1 (OPi6 provisional) | https://www.chiefdelphi.com/t/photonvision-2026-releases-2026-3-4/512436/20 |
| Orange Pi alternative (custom FRC board thread) | https://www.chiefdelphi.com/t/orange-pi-alternative-for-photonvision-hardware/503918 |
| PhotonVision hardware advice thread | https://www.chiefdelphi.com/t/photonvision-hardware-advice/508076 |
| PV Common Hardware Setups (official docs) | https://docs.photonvision.org/en/latest/docs/quick-start/common-setups.html |
| PV Selecting Hardware (official docs) | https://docs.photonvision.org/en/latest/docs/hardware/selecting-hardware.html |
| PV Rubik Pi 3 Object Detection docs | https://docs.photonvision.org/en/latest/docs/objectDetection/rubik.html |
| Qualcomm QCS6490 product page | https://www.qualcomm.com/internet-of-things/products/q6-series/qcs6490 |
| AndyMark Rubik Pi 3 Vision Bundle | https://andymark.com/products/rubik-pi3-vision-bundle |
| Anand's Coprocessor Roundup (historical reference) | https://www.chiefdelphi.com/t/anands-coprocessor-roundup-which-is-best-also-an-orange-pi-setup-guide/420981 |
