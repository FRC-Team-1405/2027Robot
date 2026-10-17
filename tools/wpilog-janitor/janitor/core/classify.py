"""What kind of entry is this, and is it safe to drop?

AdvantageKit logs fall into a few groups that matter when deciding what to delete:

  output        `/RealOutputs/...` (or `/ReplayOutputs/...`): values the robot code *computed*. Replay
                regenerates them from the inputs, so they are safe to drop as far as `simulateJava` is
                concerned -- but tools that read them (logbench reads `RealOutputs/Vision/...`) need them.
  replay-input  everything else: written by `Logger.processInputs(...)` and AdvantageKit's own DriverStation
                inputs. Replay *reads these back*, so removing one silently changes what replay does.
  structural    the cycle marker `/Timestamp` and the struct schemas `/.schema/...`. Without the schemas,
                AdvantageScope cannot decode Pose2d / Pose3d / ... values in the file.
  janitor       entries written by this tool (the original-time map).

"Protect" is a set of profiles the user picks; an entry is protected if any selected profile covers it.
Excluding a protected entry is allowed but needs an explicit override in the UI.
"""
from typing import Collection, Optional

OUTPUT = 'output'
REPLAY_INPUT = 'replay-input'
STRUCTURAL = 'structural'
JANITOR = 'janitor'
CLASSES = (OUTPUT, REPLAY_INPUT, STRUCTURAL, JANITOR)

PROFILE_REPLAY = 'replay'
PROFILE_LOGBENCH = 'logbench'
PROFILES = (PROFILE_REPLAY, PROFILE_LOGBENCH)

# What logbench / vision-analyzer look up (see logbench/server/core/signals.py and
# vision_analyzer.metrics.find_drivetrain_speeds). Each is read both bare and under RealOutputs/.
# tests/test_classify.py runs their real lookups on a sample log and checks every signal they pick
# is covered here, so this list cannot silently fall behind them.
LOGBENCH_PREFIXES = (
    'Vision', 'Drivetrain', 'Drive', 'SwerveDrivetrain', 'Swerve',
    'RealOutputs/Vision', 'RealOutputs/Drivetrain', 'RealOutputs/Drive',
    'RealOutputs/SwerveDrivetrain', 'RealOutputs/Swerve',
    'DriverStation',
)

_OUTPUT_TOPS = ('RealOutputs', 'ReplayOutputs')


def _norm(name: str) -> str:
    return name.lstrip('/')


def classify(name: str, type_: str = '') -> str:
    n = _norm(name)
    top = n.split('/', 1)[0]
    if n == 'Timestamp' or top == '.schema' or type_ == 'structschema':
        return STRUCTURAL
    if top == 'Janitor':
        return JANITOR
    if top in _OUTPUT_TOPS:
        return OUTPUT
    return REPLAY_INPUT


def under(name: str, prefix: str) -> bool:
    n = _norm(name)
    return n == prefix or n.startswith(prefix + '/')


def protection(name: str, type_: str, protect: Collection[str]) -> Optional[str]:
    """Why this entry should not be dropped, or None if nothing the user chose to protect covers it."""
    cls = classify(name, type_)
    if cls == STRUCTURAL:
        return 'structural: AdvantageScope needs this to read the log (cycle marker or struct schema)'
    if cls == JANITOR:
        return 'written by wpilog-janitor: it holds the original-time map of a trimmed log'
    if PROFILE_REPLAY in protect and cls == REPLAY_INPUT:
        return 'replay input: simulateJava replay reads this back from the log'
    if PROFILE_LOGBENCH in protect and any(under(name, p) for p in LOGBENCH_PREFIXES):
        return 'read by logbench: logbench and vision-analyzer look this up'
    return None
