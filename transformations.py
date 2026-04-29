# transformations.py
# From: https://github.com/velocitek/vtk_protocol
# Geometric transformation utilities used by vtktool.py

import math

def euler_from_quaternion(quaternion):
    """
    Convert a quaternion to Euler angles (heading, heel/roll, pitch).
    Returns (heading_deg, heel_deg, pitch_deg)
    """
    x = quaternion.x
    y = quaternion.y
    z = quaternion.z
    w = quaternion.w

    # Roll (heel) - rotation around X axis
    sinr_cosp = 2 * (w * x + y * z)
    cosr_cosp = 1 - 2 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # Pitch - rotation around Y axis
    sinp = 2 * (w * y - z * x)
    if abs(sinp) >= 1:
        pitch = math.copysign(math.pi / 2, sinp)
    else:
        pitch = math.asin(sinp)

    # Yaw (heading) - rotation around Z axis
    siny_cosp = 2 * (w * z + x * y)
    cosy_cosp = 1 - 2 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    heading_deg = math.degrees(yaw) % 360
    heel_deg    = math.degrees(roll)
    pitch_deg   = math.degrees(pitch)

    return heading_deg, heel_deg, pitch_deg
