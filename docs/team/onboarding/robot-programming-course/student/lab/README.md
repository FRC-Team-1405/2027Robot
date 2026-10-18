# Java elevator lab
## Run
Open a terminal in this directory. Check `java --version`. Use a **full JDK**, not a runtime-only install. If `java` is not found, select the installed JDK or use the WPILib terminal after installing WPILib.

```sh
java RobotLab.java
```

The first window shows a blue elevator and green target. Start with Automatic off. Check Enabled and move the manual slider; its integer value divided by 10 is volts (20 means +2 V). The target slider is centimeters (80 means 0.80 m). Reset unchecks Enabled, returns the plant to 0.20 m, and clears the run. Controls remain where you left them; set them for each trial. Disabled output is zero, so the elevator can fall under gravity: disabled is not a hold command.

The source launcher compiles and runs this file without a separate build command. Save, close the old window, and rerun after editing. Edit only the StudentController area until lesson 06. The lab ships with intentional unfinished behavior and failing lesson checks.

## Repeatable runs without a window
```sh
java RobotLab.java --headless manual manual-before.csv
java RobotLab.java --headless auto auto-before.csv
java RobotLab.java --headless disabled disabled.csv
java RobotLab.java --test 02
```

Tests exist for 02, 03, 04, 07, 08. A failed check prints FAIL and exits with nonzero status. A successful check prints PASS. Run the check for the current lesson; future checks intentionally fail before you implement their concepts. Copy terminal output into your evidence file. On macOS/Linux `> checks.txt 2>&1` redirects output; in PowerShell use `*> checks.txt`.

Every headless run starts at 0.20 m at rest, runs 600 steps at 0.020 s each, and writes 600 samples. Manual mode requests +2 V. Automatic requests targets 0.80 m during [0,4), 1.20 m during [4,8), then 0.30 m during [8,12). The CSV timestamp describes the completed step, so the new target first appears at 4.02 and 8.02 s. Disabled applies zero voltage for the whole run. Samples contain post-step height/velocity and the voltage used during that step.

CSV columns have units in their names. Use a spreadsheet or plotting tool to plot time_s on X and target_m / height_m on Y. The GUI has a rolling height graph; CSV preserves exact evidence. This CSV is not a WPILib log and is not promised to import directly into AdvantageScope. The WPILib stage uses WPILib logs.

## Model contract
`velocity += (2*appliedVolts - 1 - 3*velocity)*0.020`, then `height += velocity*0.020`. Physical travel is 0..1.50 m. Software travel limits are 0.05..1.45 m. A simulated motor saturates at ±12 V; student code must enforce a stricter ±6 V policy. These coefficients are teaching values, not measured robot constants. Hard stops prevent penetration; they do not test whether your code requested unsafe motion.

GUI timers may run slower than real time on a busy computer. Simulated time advances a fixed 20 ms each tick; headless runs do not wait in real time. Reset before comparisons. Long GUI sessions keep samples in memory: export and reset between experiments.

## If something goes wrong
- `class ...` / syntax errors: inspect the first error, missing semicolons, braces, and the named line. Save before rerunning.
- Window unavailable on a remote/headless machine: use --headless and plot the CSV on your computer.
- Elevator falls when disabled: expected gravity; inspect requested_V and applied_V.
- Automatic does nothing initially: its calculation is a student exercise.
- Target changes but height does not follow: inspect voltage and calculate(), not only the drawing.
- Need help: submit the command, first error, source snapshot, and prediction. Do not send only “broken.”
