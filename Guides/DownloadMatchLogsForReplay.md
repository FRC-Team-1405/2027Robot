# FRC Match Log Review Guide – Team 1405

Guide is WIP, has not been tested!

TODO rework this guide and use the DataLog tool to download the wpilog file instead of sshing into the robot. reducing complexity of steps.

This guide explains how to download `.wpilog` files from the robot after a competition match and load them into AdvantageScope for telemetry review and match replay.

## Prerequisites

- A laptop with SSH access to the roboRIO
- AdvantageScope installed: https://docs.advantagescope.org/
- Latest AdvantageScope layout is applied, see repo ex. AdvantageScope-layout.json
- `.wpilog` files generated during the match using WPILib logging or AdvantageKit

## Step 1: Download Logs from the Robot

After the match, connect your laptop to the robot’s network (via USB or Ethernet tether) and follow these steps to download .wpilog files using the WPILib Data Log Tool.

1. Prepare your laptop
   - Ensure your laptop is on the same network as the roboRIO (USB or Ethernet tether).
   - Verify name resolution (mDNS) works for the roboRIO hostname (for example: roborio-1405-FRC.local). If mDNS is unreliable, use the roboRIO IP address.

2. Open the WPILib Data Log Tool
3. Connect to the roboRIO
   - In the Data Log Tool, enter the roboRIO hostname or IP (for example: roborio-1405-FRC.local) and connect.

4. Locate and download .wpilog files
   - In the tool’s file/listing view you should see available .wpilog files (they are usually listed with timestamps).
   - Select the log(s) you want and click the Download / Save button.
   - Choose a local destination folder on your laptop and save the files.
   - If at a competition you MUST ENSURE that the logs are saved in at least two places. Copy logs to a USB stick before deleting them on the roborio. If the roborio has plenty of space, leave logs on the robot until after competition is over.

5. (Likely not needed) If logs are on an attached USB stick
   - If a USB stick was plugged into the roboRIO (logs saved to /media/sda1 or /media/sdb1), look for those files in the Data Log Tool’s file browser or mounted media listing.
   - If the Data Log Tool does not show the media location, remove the USB stick and plug it into your laptop to copy files directly.

## Step 2: Load the Log into AdvantageScope

1. Open AdvantageScope on your laptop.
2. Go to `File > Open Log(s)...`
3. Select the `.wpilog` file you downloaded.
4. Use the interface to explore telemetry:
- View subsystem data
- Analyze command lifecycles
- Inspect drivetrain paths, sensor readings, and more
- Sync with match video if available

## Optional: Organize Logs by Match

Rename logs for clarity:

<b>FRC_20250830_154700.wpilog -> QualMatch3_RedAlliance.wpilog</b>

mv FRC_20250830_154700.wpilog QualMatch3_RedAlliance.wpilog

## Troubleshooting

- No logs found: Ensure logging was enabled in your robot code using `DataLogManager` or `@Logged` annotations.
- Can't connect to roboRIO: Try using the IP address `10.14.05.2` instead of mDNS.
- AdvantageScope not showing data: Confirm that your fields are properly annotated or published to NetworkTables.

## Resources

- AdvantageScope Documentation: https://docs.advantagescope.org/
- WPILib Logging Guide: https://docs.wpilib.org/en/stable/docs/software/wpilib-tools/data-logging.html
- AdvantageKit (not currently used): https://docs.advantagekit.org/
