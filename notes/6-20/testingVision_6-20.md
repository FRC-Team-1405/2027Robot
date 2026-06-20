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