import pathlib
import sys

_TOOLS = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_TOOLS / 'wpilog-janitor'))            # janitor
sys.path.insert(0, str(_TOOLS / 'wpilog-utils'))              # wpilog_utils
sys.path.insert(0, str(_TOOLS / 'wpilog-utils' / 'tests'))    # wpilog_builder (shared synthetic-log builder)
