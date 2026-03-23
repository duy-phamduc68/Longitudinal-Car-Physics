# ─────────────────────────────────────────────────────────────────────────────
# physics.py — CarModel and GraphBuffer
# ─────────────────────────────────────────────────────────────────────────────

import math
import collections

from constants import (
    M,
    C_RR,
    C_DRAG,
    C_BRAKE_TORQUE,
    I_W,
    MU,
    g,
    L,
    h,
    b,
    c,
)
from engine import EngineModel


class CarModel:
    """1-D longitudinal vehicle dynamics model."""

    def __init__(self):
        self.x = 0.0
        self.v = 0.0
        self.omega = 0.0
        self.wheel_angle = 0.0
        self.engine = EngineModel()
        # Instance-level constants so options menu can vary them per scenario
        self.M            = M
        self.I_W          = I_W
        self.C_RR         = C_RR
        self.C_DRAG       = C_DRAG
        self.C_BRAKE_TORQUE    = C_BRAKE_TORQUE
        self.MU           = MU
        self.g            = g
        self.L            = L
        self.h            = h
        self.b            = b
        self.c            = c

        # Model 4 derived state (updated every step and available to renderer)
        self.W            = self.M * self.g
        self.dW           = 0.0
        self.Wf_static    = (self.c / self.L) * self.W
        self.Wr_static    = (self.b / self.L) * self.W
        self.Wf           = self.Wf_static
        self.Wr           = self.Wr_static

    def _update_load_state(self, a):
        self.W         = self.M * self.g
        self.dW        = (self.h / self.L) * self.M * a
        self.Wf_static = (self.c / self.L) * self.W
        self.Wr_static = (self.b / self.L) * self.W
        self.Wf        = self.Wf_static - self.dW
        self.Wr        = self.Wr_static + self.dW

    def reset(self):
        """Reset kinematic state only; constants are preserved."""
        self.x = 0.0
        self.v = 0.0
        self.wheel_angle = 0.0
        self.engine.reset()
        self._update_load_state(0.0)

    @property
    def gear(self):
        return self.engine.gear

    @gear.setter
    def gear(self, value):
        self.engine.gear = value

    @property
    def rpm(self):
        return self.engine.rpm

    @rpm.setter
    def rpm(self, value):
        self.engine.rpm = value

    @property
    def R_W(self):
        return self.engine.R_W

    @R_W.setter
    def R_W(self, value):
        self.engine.R_W = value

    @property
    def FINAL_DRIVE(self):
        return self.engine.FINAL_DRIVE

    @FINAL_DRIVE.setter
    def FINAL_DRIVE(self, value):
        self.engine.FINAL_DRIVE = value

    @property
    def ETA(self):
        return self.engine.ETA

    @ETA.setter
    def ETA(self, value):
        self.engine.ETA = value

    @property
    def GEAR_RATIOS(self):
        return self.engine.GEAR_RATIOS

    @GEAR_RATIOS.setter
    def GEAR_RATIOS(self, value):
        self.engine.GEAR_RATIOS = dict(value)

    @property
    def RPM_IDLE(self):
        return self.engine.RPM_IDLE

    @RPM_IDLE.setter
    def RPM_IDLE(self, value):
        self.engine.RPM_IDLE = value

    @property
    def RPM_REDLINE(self):
        return self.engine.RPM_REDLINE

    @RPM_REDLINE.setter
    def RPM_REDLINE(self, value):
        self.engine.RPM_REDLINE = value

    @property
    def TORQUE_CURVE(self):
        return self.engine.TORQUE_CURVE

    @TORQUE_CURVE.setter
    def TORQUE_CURVE(self, value):
        self.engine.TORQUE_CURVE = list(value)

    def update(self, dt, u, B):
        v_prev = self.v
        
        # 1. Get Drive Torque from Engine
        T_drive, _rpm, _gear = self.engine.update(v_prev, u, B, dt)

        # 2. Linear Resistances
        F_rr     = self.C_RR  * v_prev
        F_drag   = self.C_DRAG * v_prev * abs(v_prev)

        # 3. Braking Torque (Acts on wheels now)
        if abs(self.omega) > 0.01:
            T_brake = self.C_BRAKE_TORQUE * B * math.copysign(1.0, self.omega)
        else:
            T_brake = 0.0

        # 4. THE MODEL 4 HACK (Effective Mass Integration)
        # M_eff = M + I_w / R_w^2
        M_eff = self.M + (self.I_W / (self.engine.R_W ** 2))
        
        # Combine ODEs mechanically
        F_net = ((T_drive - T_brake) / self.engine.R_W) - F_rr - F_drag
        a = F_net / M_eff

        self.v = v_prev + dt * a

        # Settle logic for braking
        if B > 0 and v_prev * self.v < 0:
            self.v = 0.0
            a = 0.0
        if abs(self.v) < 0.03 and abs(u) < 0.03:
            self.v = 0.0
            a = 0.0
        if abs(self.v) < 0.15 and B > 0.05 and abs(u) < 0.08:
            self.v = 0.0
            a = 0.0

        # 5. Update Wheel State (The Constraint)
        self.omega = self.v / max(self.engine.R_W, 1e-6)
        alpha_wheel = a / max(self.engine.R_W, 1e-6)
        self.wheel_angle = (self.wheel_angle + self.omega * dt) % (2.0 * math.pi)
        self.x = self.x + dt * self.v

        self._update_load_state(a)

        # 6. CALCULATE "CHEAT" UI VALUES
        # If the car is perfectly glued, Net Torque MUST equal I_w * alpha
        net_torque_star = self.I_W * alpha_wheel
        
        # To balance the equation, Traction Torque is whatever is left over.
        # (Inside the deadzone, this acts as perfect Static Friction!)
        T_traction_star = T_drive - T_brake - net_torque_star
        
        # Traction Force is just that torque divided by radius
        F_traction_star = T_traction_star / self.engine.R_W
        
        F_net_linear    = self.M * a
        slip_star       = 0.0

        # Return all 14 channels
        return [
            self.v, a, self.x, F_traction_star, F_drag, F_rr, F_net_linear,
            self.omega, alpha_wheel, slip_star, T_drive, T_brake, T_traction_star, net_torque_star
        ]


class GraphBuffer:
    """Circular buffer holding the last WINDOW seconds of telemetry per channel."""

    CHANNELS = 14
    WINDOW   = 30.0   # seconds

    def __init__(self, dt):
        self._dt      = dt
        self._max_pts = max(1, int(self.WINDOW / dt) + 10)
        self._bufs    = [collections.deque(maxlen=self._max_pts)
                         for _ in range(self.CHANNELS)]
        self._times   = collections.deque(maxlen=self._max_pts)

    def reset(self, new_dt=None):
        if new_dt is not None:
            self._dt      = new_dt
            self._max_pts = max(1, int(self.WINDOW / new_dt) + 10)
            self._bufs    = [collections.deque(maxlen=self._max_pts)
                             for _ in range(self.CHANNELS)]
            self._times   = collections.deque(maxlen=self._max_pts)
        else:
            for b in self._bufs:
                b.clear()
            self._times.clear()

    def push(self, t, values):
        """Push one sample; values = [v, a, x, F_eng, F_drag, F_rr, F_brake]."""
        self._times.append(t)
        for i, val in enumerate(values[:self.CHANNELS]):
            self._bufs[i].append(val)

    def get(self, channel):
        return list(self._bufs[channel])

    def get_times(self):
        return list(self._times)
