# FRC Software Team Competition Checklist

## Pre-Competition Preparation

### Code & Version Control
- Create a new Git branch off main for the specific competition (e.g., 2025_FLR)

### Documentation & Printouts
- Print joystick/controller mappings for driver and operator
  - Include all modes (place element, retrive element, manual, endgame)
- Print cheat sheets for:
  - Autonomous routine selection
  - LED signaling or status indicators
  - Emergency override procedures
  - Field layout with tag positions

### Pack These Essentials
- Laptop(s) with fully updated development environment
  - Has the latest software tools (VS Code, WPILib, Gradle)
  - Has the latest dashboard layouts applied (Elastic, AdvantageScope)
- USB A-to-B (printer) cable to connect to roborio and USB-C adapters
- Camera calibration board (ChArUco 5x5)
- A few AprilTags (36h11 family, IDs 1–22)
- Flash drives with:
  - Latest robot code
  - Calibration data (for ideal field)
- Ethernet cables
- Power strip / Extension cords
- April Tags
- hdmi cable for scouting meeting

### Good Spares to have
- Two spare controllers
- 2 spare rio's
- 2 spare micro SD cards
- 2 spare radios
- 2 spare camera's

### Robot Prep
- Clear out roborio deploy directory of any logs and ensure roborio has plenty of spare drive space

## At the Competition

### Setup & Connectivity
- Connect to field Wi-Fi and verify robot IP
- Test DS connection and joystick recognition
- Run a full system check (motors, pneumatics, sensors)

### Calibration & Vision
- Recalibrate camera if lighting conditions differ significantly
- Verify AprilTag detection and pose estimation
- Confirm camera stream is visible on dashboard (if applicable)
- During the field calibration time block, record a video on a smartphone of all the april tags to be processed in WPICal to produce field specific april tag layout .json file and .fmap file for camera co processor
- During field calibration time block, perform measurements of key field elements relative to the april tags and input discrepencies into the Field Correction Map

### Autonomous Routine Prep
- Verify auto selector is working on dashboard
- Test each autonomous routine on practice field
- Adjust trajectories if field tolerances differ

### Logging & Debugging
- Enable telemetry and log important metrics (battery, CPU, loop time)
- Record match logs for post-match debugging
- Use Shuffleboard/Glass to monitor key subsystems

### Contingency Plans
- Have a fallback autonomous routine (e.g., drive forward and stop)
  - if advantagekit recordings of auto's exist can we replay those directly on the motors?
- Know how to disable subsystems quickly in code if needed
- Keep a list of known bugs and workarounds

## Post-Match Routine
- Download logs and review performance
- Check for brownouts, CAN errors, or missed packets
- Reboot robot and DS between matches
- Communicate any issues to drive team and pit crew