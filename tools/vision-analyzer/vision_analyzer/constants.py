"""
Field geometry, AprilTag positions, robot connectivity addresses, and camera colors.
"""
from typing import Dict, Tuple

FIELD_LENGTH = 16.541   # meters, 2026 Reefscape rebuilt-welded
FIELD_WIDTH  = 8.069

# Exact positions from src/main/deploy/2026-rebuilt-welded.json
APRILTAG_POSITIONS: Dict[int, Tuple[float, float]] = {
    1:  (11.878, 7.425),   2:  (11.915, 4.638),   3:  (11.312, 4.390),
    4:  (11.312, 4.035),   5:  (11.915, 3.431),   6:  (11.878, 0.644),
    7:  (11.953, 0.644),   8:  (12.271, 3.431),   9:  (12.519, 3.679),
    10: (12.519, 4.035),   11: (12.271, 4.638),   12: (11.953, 7.425),
    13: (16.533, 7.403),   14: (16.533, 6.972),   15: (16.533, 4.324),
    16: (16.533, 3.892),   17: (4.663,  0.644),   18: (4.626,  3.431),
    19: (5.229,  3.679),   20: (5.229,  4.035),   21: (4.626,  4.638),
    22: (4.663,  7.425),   23: (4.588,  7.425),   24: (4.270,  4.638),
    25: (4.022,  4.390),   26: (4.022,  4.035),   27: (4.270,  3.431),
    28: (4.588,  0.644),   29: (0.008,  0.666),   30: (0.008,  1.098),
    31: (0.008,  3.746),   32: (0.008,  4.178),
}

REEF_TAG_IDS = frozenset({6, 7, 8, 9, 10, 11, 17, 18, 19, 20, 21, 22})

POSE2D_SIZE = 24   # double x, double y, double rotation_radians
POSE3D_SIZE = 56   # double x,y,z, double qw,qx,qy,qz

# Robot connectivity
_ROBORIO_HOSTS  = ['roborio-1405-frc.local', '10.14.5.2', '172.22.11.2']
_ROBORIO_USER   = 'lvuser'
_ROBORIO_PASS   = ''
_ROBOT_LOG_DIR  = '/home/lvuser/logs'

# Camera colors
_COLORS = {
    'Left':  {'primary': '#4FC3F7', 'secondary': '#0288D1'},
    'Right': {'primary': '#AED581', 'secondary': '#558B2F'},
}
_DEFAULT_COLOR = {'primary': '#FFB74D', 'secondary': '#E65100'}


def _cam_color(camera: str, role: str = 'primary') -> str:
    return _COLORS.get(camera, _DEFAULT_COLOR)[role]
