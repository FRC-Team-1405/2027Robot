# 00 · Make a repeatable first run

No programming prerequisites. Learn the difference between source text, the Java launcher, and a running program.

Work in small steps. For each checkpoint, copy templates/SUBMISSION.md into your named submission folder. Include a source snapshot, exact commands, evidence, and answers. Do not overwrite an earlier attempt.

## Checkpoint A — Run the unchanged program

**Learn:** A program is a set of instructions stored as text. Editing a file does not change an already-running process. A terminal runs a command in a particular folder.

**Do:** Open student/lab/README.md. Run java --version, then java RobotLab.java --headless manual baseline.csv. Open the CSV as text. Find the header and first data row. Record which folder received the file.

**Submit:** A version record, the exact command, the unchanged source snapshot, and baseline.csv. Expect 600 data rows plus one header.

**Explain:** If you edit the file after launching it, why does the running program keep its old behavior?

## Checkpoint B — See motion

**Learn:** A sensor measurement is what the system reports. A command is what you ask it to do. A drawing should show the measurement.

**Do:** Run the GUI. Reset, set manual to +2 V, Automatic off, enable, and observe for 2 simulated seconds. Export with a new filename. Repeat at -2 V from reset. If no GUI is available, use manual and disabled scenarios and plot their CSVs.

**Submit:** Two observations with starting conditions and a screenshot or plot. Identify target, measured height, requested voltage, and applied voltage.

**Explain:** Can the green target move even if the elevator does not? What would that tell you?

## Checkpoint C — Recover from an error

**Learn:** A compiler error prevents execution. A behavior bug can run and still do the wrong thing.

**Do:** In a disposable copy, remove the semicolon from double kP = 0.0;. Run it and save the first error. Restore the semicolon and rerun. Keep the working file.

**Submit:** The error text, a one-sentence diagnosis, and a successful rerun.

**Explain:** How would you distinguish a syntax error from an elevator moving in the wrong direction?

## Ready to move on

You can reproduce your result from a clean start and explain it without reading a solution. Mark the submission ready-for-review. If feedback requests a change, create another attempt and describe what you learned.
