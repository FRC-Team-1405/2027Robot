import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))     # wpilog_utils
sys.path.insert(0, str(_HERE))            # wpilog_builder
