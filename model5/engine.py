# -----------------------------------------------------------------------------
# engine.py - Drivetrain / engine model (RPM, gears, torque, wheel force)
# -----------------------------------------------------------------------------

import math

from constants import (
    R_W,
    FINAL_DRIVE,
    ETA,
    GEAR_RATIOS,
    RPM_IDLE,
    RPM_REDLINE,
    TORQUE_CURVE,
    UPSHIFT_RPM,
    DOWNSHIFT_RPM,
    get_max_torque,
)


class EngineModel:
    def __init__(self):
        self.R_W = R_W
        self.FINAL_DRIVE = FINAL_DRIVE
        self.ETA = ETA
        self.GEAR_RATIOS = dict(GEAR_RATIOS)
        self.RPM_IDLE = RPM_IDLE
        self.RPM_REDLINE = RPM_REDLINE
        self.TORQUE_CURVE = list(TORQUE_CURVE)

        self.upshift_rpm = UPSHIFT_RPM
        self.downshift_rpm = DOWNSHIFT_RPM
        self.enable_auto_shift = False

        self.gear = 1
        self.rpm = self.RPM_IDLE

    def reset(self):
        self.gear = 1
        self.rpm = self.RPM_IDLE

    def request_shift(self, delta):
        max_fwd_gear = max((g for g in self.GEAR_RATIOS.keys() if g > 0), default=5)
        self.gear = max(-1, min(max_fwd_gear, self.gear + delta))

    def _apply_auto_shift_hysteresis(self):
        if not self.enable_auto_shift:
            return
        if self.gear < 1:
            return

        up = float(self.upshift_rpm)
        down = float(self.downshift_rpm)
        if down >= up:
            down = up - 200.0

        max_fwd_gear = max((g for g in self.GEAR_RATIOS.keys() if g > 0), default=5)
        if self.rpm > up and self.gear < max_fwd_gear:
            self.gear += 1
        elif self.rpm < down and self.gear > 1:
            self.gear -= 1

    def update(self, v, throttle, brake, dt):
        self._apply_auto_shift_hysteresis()

        omega_wheel = v / max(self.R_W, 1e-6)
        gear_ratio = self.GEAR_RATIOS.get(self.gear, 0.0)

        if self.gear == 0:
            rpm = self.RPM_IDLE
        else:
            rpm = abs(omega_wheel * gear_ratio * self.FINAL_DRIVE * 60 / (2 * math.pi))
            rpm = max(rpm, self.RPM_IDLE)

        self.rpm = rpm

        if self.rpm >= self.RPM_REDLINE:
            t_engine = 0.0
        else:
            t_engine = throttle * get_max_torque(self.rpm, self.TORQUE_CURVE)

        # Output pure Torque (T_drive) instead of Force
        t_drive = t_engine * gear_ratio * self.FINAL_DRIVE * self.ETA

        if self.gear < 0:
            t_drive = -t_drive

        if self.gear > 0 and v < -0.1:
            t_drive = 0.0
        if self.gear < 0 and v > 0.1:
            t_drive = 0.0

        return t_drive, self.rpm, self.gear
