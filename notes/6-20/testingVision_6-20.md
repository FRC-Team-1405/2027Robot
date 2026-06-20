# Photon Vision Camera Config Changes
- decimate: 3 -> 1
- threads: 3 -> 7
- decision margin cutoff: 35 -> 30
blur stayed at 0
refine edges stayed true
pose estimation iterations stayed 100


## Issue with log comparison:
2026-06-20 11:02:20.001 Uncaught app execution
Traceback (most recent call last):
  File "C:\Users\FinneyRobotics\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\streamlit\runtime\scriptrunner\exec_code.py", line 129, in exec_func_with_error_handling
    result = func()
  File "C:\Users\FinneyRobotics\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\streamlit\runtime\scriptrunner\script_runner.py", line 789, in code_to_exec
    exec(code, module.__dict__)  # noqa: S102
    ~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\FinneyRobotics\VS Code\2027Robot\tools\vision-analyzer\analyze.py", line 11, in <module>
    _streamlit_app()
    ~~~~~~~~~~~~~~^^
  File "C:\Users\FinneyRobotics\VS Code\2027Robot\tools\vision-analyzer\vision_analyzer\app.py", line 564, in _streamlit_app
    tab_module.render(ctx)
    ~~~~~~~~~~~~~~~~~^^^^^
  File "C:\Users\FinneyRobotics\VS Code\2027Robot\tools\vision-analyzer\vision_analyzer\tabs\summary.py", line 145, in render
    table_a[m['camera']] = [rows_a[mn][i] for i, mn in enumerate(metric_names)]
                            ~~~~~~~~~~^^^
IndexError: list index out of range


## Phton vision redo decimate
moving decimate from 3 to 1 caused significant reduction in vision performance. I moved it back to 3 and will analyze the difference between camera config changes without the decimate change.


## latest robot log download hanging
it doesn't ever complete the download, no errors, no indication of progress (if any)

Log:
2026-06-20 11:21:08  INFO      vision_analyzer.robot  Starting robot log download — suffix=''  dest=C:\Users\FinneyRobotics\VS Code\2027Robot\logs
2026-06-20 11:21:08  DEBUG     vision_analyzer.robot  Attempting SSH connection to roborio-1405-frc.local (user=lvuser)
2026-06-20 11:21:10  INFO      vision_analyzer.robot  SSH connected to roboRIO at roborio-1405-frc.local
2026-06-20 11:21:10  DEBUG     vision_analyzer.robot  Opening SFTP channel
2026-06-20 11:21:11  DEBUG     vision_analyzer.robot  Found 442 total entries in /home/lvuser/logs, 220 are .wpilog files
2026-06-20 11:21:11  INFO      vision_analyzer.robot  Downloading /home/lvuser/logs/FRC_20260620_152018.wpilog (remote mtime=1781968871) -> C:\Users\FinneyRobotics\VS Code\2027Robot\logs\FRC_20260620_152018.wpilog
