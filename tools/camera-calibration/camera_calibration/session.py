"""Physical tape-measure → robot pose conversions with step-by-step breakdown."""
import math


def compute_x_in(tape_a_in: float, bumper_depth_in: float, half_length_in: float) -> float:
    """Robot center perpendicular distance from tag face plane, in inches."""
    return tape_a_in + bumper_depth_in + half_length_in


def compute_y_in(tape_b_in: float, half_width_in: float, side: str) -> float:
    """Lateral offset from tag centerline to robot center, in inches.

    tape_b_in : unsigned distance from tag centerline to nearest bumper rail edge
    side      : 'left'  → robot center is to the left  of the tag (from robot's POV facing tag)
                'right' → robot center is to the right of the tag

    The calibration frame's +Y is defined by X×Y=Z (X = tag-face-outward, Z = up),
    which makes +Y the tag's own left as it "looks" outward — i.e. the robot's
    RIGHT when the robot stands facing the tag. So:
        Positive y = robot's right = tag's +Y direction.
        Negative y = robot's left  = tag's −Y direction.
    """
    sign = -1 if side == 'left' else +1
    return sign * (tape_b_in + half_width_in)


def compute_heading_deg(corner_l_in: float, corner_r_in: float,
                        bumper_rail_width_in: float) -> float:
    """Heading in degrees (CCW positive, 0 = facing tag straight-on).

    corner_l_in / corner_r_in : distances from each FRONT bumper corner to the
        TAG FACE WALL (or any parallel reference plane).  Smaller = closer to wall.

    Convention: left corner farther from wall than right corner → robot rotated CCW
    → positive heading. (A CCW turn, viewed from above, swings the robot's right
    side toward the wall and its left side away from it.)

        heading = atan2(corner_l − corner_r, bumper_rail_width)
    """
    return math.degrees(math.atan2(corner_l_in - corner_r_in, bumper_rail_width_in))


def user_heading_to_wpilib_yaw(heading_user_deg: float) -> float:
    """Map user-facing heading (0 = facing tag) to WPILib yaw (0 = facing field +X).

    When the robot faces the tag it faces along the tag's −X axis, which in the
    calibration frame is the −X direction → WPILib yaw = 180°.
    WPILib yaw is CCW-positive (increases going CCW, viewed from above), so a
    CCW turn (positive user heading) increases WPILib yaw:
        yaw_wpilib = 180° + heading_user
    """
    return 180.0 + heading_user_deg


def math_breakdown(
    tape_a_in: float, bumper_depth_in: float, half_length_in: float,
    tape_b_in: float, half_width_in: float, side: str,
    corner_l_in: float, corner_r_in: float, bumper_rail_width_in: float,
) -> list[tuple[str, str, str]]:
    """Return list of (name, formula_string, result_string) for educational display.

    Each tuple describes one step of the position/heading computation so students
    can follow the arithmetic.
    """
    x_in   = compute_x_in(tape_a_in, bumper_depth_in, half_length_in)
    y_in   = compute_y_in(tape_b_in, half_width_in, side)
    h_deg  = compute_heading_deg(corner_l_in, corner_r_in, bumper_rail_width_in)
    x_m    = x_in * 0.0254
    y_m    = y_in * 0.0254
    c_diff = corner_l_in - corner_r_in
    sign   = '−' if side == 'left' else '+'

    return [
        ('X position (in)',
         f'Tape A + bumper depth + ½ length  '
         f'= {tape_a_in:.2f} + {bumper_depth_in:.2f} + {half_length_in:.2f}',
         f'{x_in:.3f} in'),

        ('X position (m)',
         f'{x_in:.3f} in × 0.0254',
         f'{x_m:.4f} m'),

        ('Y position (in)',
         f'{sign}(Tape B + ½ width)  '
         f'= {sign}({tape_b_in:.2f} + {half_width_in:.2f})',
         f'{y_in:.3f} in'),

        ('Y position (m)',
         f'{abs(y_in):.3f} in × 0.0254 × ({sign}1)',
         f'{y_m:.4f} m'),

        ('Corner diff (in)',
         f'Corner L − Corner R  = {corner_l_in:.2f} − {corner_r_in:.2f}',
         f'{c_diff:.3f} in'),

        ('Heading (°)',
         f'atan2({c_diff:.3f}, {bumper_rail_width_in:.2f})',
         f'{h_deg:.2f}°'),
    ]
