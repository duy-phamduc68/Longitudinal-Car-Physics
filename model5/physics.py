# ─────────────────────────────────────────────────────────────────────────────
# physics.py — CarModel and GraphBuffer
# ─────────────────────────────────────────────────────────────────────────────

import math
import collections

from constants import (
    M, C_RR, C_DRAG, C_BRAKE_TORQUE, I_W, MU, C_T, g, L, h, b, c,
)
from engine import EngineModel

class CarModel:
    """1-D longitudinal vehicle dynamics model (Model 5 - Fully Decoupled)."""

    def __init__(self):
        self.x = 0.0
        self.v = 0.0
        self.omega = 0.0
        self.wheel_angle = 0.0
        self.engine = EngineModel()
        
        # Instance-level constants
        self.M            = M
        self.I_W          = I_W
        self.C_RR         = C_RR
        self.C_DRAG       = C_DRAG
        self.C_BRAKE_TORQUE = C_BRAKE_TORQUE
        self.MU           = MU
        self.C_T          = C_T
        self.g            = g
        self.L            = L
        self.h            = h
        self.b            = b
        self.c            = c

        self.W            = self.M * self.g
        self.dW           = 0.0
        self.Wf_static    = (self.c / self.L) * self.W
        self.Wr_static    = (self.b / self.L) * self.W
        self.Wf           = self.Wf_static
        self.Wr           = self.Wr_static
        
        from constants import CAR_BODY
        self.chassis_color = CAR_BODY

        self.is_slipping  = False

    def _update_load_state(self, a):
        self.W         = self.M * self.g
        self.dW        = (self.h / self.L) * self.M * a
        self.Wf_static = (self.c / self.L) * self.W
        self.Wr_static = (self.b / self.L) * self.W
        self.Wf        = max(0.0, self.Wf_static - self.dW)
        self.Wr        = max(0.0, self.Wr_static + self.dW)

    def reset(self):
        self.x = 0.0
        self.v = 0.0
        self.omega = 0.0
        self.wheel_angle = 0.0
        self.is_slipping = False
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
        omega_prev = self.omega
        
        # 1. Get Drive Torque from Engine
        T_drive, _rpm, _gear = self.engine.update(omega_prev, v_prev, u, B, dt)

        # ---------------------------------------------------------
        # THE MODEL 4 HACK (Glued Tires)
        # ---------------------------------------------------------
        if not getattr(self, 'use_slip', True):
            T_brake = 0.0
            if abs(omega_prev) > 0.01:
                max_brake_t = (self.I_W * abs(omega_prev)) / dt
                actual_b = min(self.C_BRAKE_TORQUE * B, max_brake_t)
                T_brake = actual_b * math.copysign(1.0, omega_prev)

            M_eff = self.M + (self.I_W / (self.engine.R_W ** 2))
            F_rr = self.C_RR * v_prev
            F_drag = self.C_DRAG * v_prev * abs(v_prev)
            
            F_net = ((T_drive - T_brake) / self.engine.R_W) - F_rr - F_drag
            a = F_net / M_eff
            
            self.v += dt * a
            
            if B > 0 and v_prev * self.v < 0: self.v = 0.0; a = 0.0
            if abs(self.v) < 0.05 and u < 0.01: self.v = 0.0; a = 0.0
            
            self.omega = self.v / max(self.engine.R_W, 1e-6)
            alpha_wheel = a / max(self.engine.R_W, 1e-6)
            self.wheel_angle = (self.wheel_angle + self.omega * dt) % (2.0 * math.pi)
            self.x += dt * self.v
            self._update_load_state(a)

            net_torque_star = self.I_W * alpha_wheel
            T_traction_star = T_drive - T_brake - net_torque_star
            self.is_slipping = False
            
            return [self.v, a, self.x, T_traction_star / self.engine.R_W, F_drag, F_rr, self.M * a,
                    self.omega, alpha_wheel, 0.0, T_drive, T_brake, T_traction_star, net_torque_star]

        # ---------------------------------------------------------
        # THE MODEL 5 PHYSICS (Game-Optimized Slip Dynamics)
        # ---------------------------------------------------------
        
        # NEW: Effective Drivetrain Inertia
        # Adds the engine's internal mass (multiplied by gearing) to the wheels
        # This acts as a massive shock-absorber for the RPM jitter!
        gear_ratio = self.engine.GEAR_RATIOS.get(self.engine.gear, 0.0)
        I_engine = 0.25 # kg·m^2 (Typical engine internal inertia)
        I_eff = self.I_W + I_engine * (gear_ratio * self.engine.FINAL_DRIVE) ** 2
        
        # 2. SMOOTH SLIP RATIO
        v_abs = max(abs(v_prev), 1.0) 
        slip_ratio = (omega_prev * self.engine.R_W - v_prev) / v_abs
        
        # 3. TRACTION CAP
        F_trac_raw = self.C_T * slip_ratio
        F_max = self.MU * self.Wr 
        F_traction = max(-F_max, min(F_max, F_trac_raw))
        T_traction = F_traction * self.engine.R_W
        self.is_slipping = abs(F_trac_raw) > F_max

        # 4. RESISTANCES & NATURAL DAMPING
        F_rr     = self.C_RR  * v_prev
        F_drag   = self.C_DRAG * v_prev * abs(v_prev)
        T_drag_wheel = 0.5 * omega_prev # Small internal wheel bearing friction

        # 5. SMART BRAKING
        T_ext = T_drive - T_traction - T_drag_wheel
        T_brake = 0.0
        
        if abs(omega_prev) > 0.1:
            # Dynamic Braking
            max_brake_t = (I_eff * abs(omega_prev)) / dt
            actual_b = min(self.C_BRAKE_TORQUE * B, max_brake_t)
            T_brake = actual_b * math.copysign(1.0, omega_prev)
        else:
            # Static Hold
            max_hold = self.C_BRAKE_TORQUE * B
            if abs(T_ext) <= max_hold:
                T_brake = T_ext 
            else:
                T_brake = max_hold * math.copysign(1.0, T_ext)

        # 6. INTEGRATION (Using the new Heavy Inertia)
        F_net = F_traction - F_drag - F_rr
        T_net = T_drive - T_brake - T_traction - T_drag_wheel

        a = F_net / self.M
        alpha = T_net / I_eff

        self.v += dt * a
        self.omega += dt * alpha
        
        # 7. THE "IRON GRIP" REVERSE/STOP FIX
        # If we are crawling and actively braking, or coasting to a total stop:
        is_braking_to_stop = (B > 0.1 and abs(self.v) < 0.5)
        is_coasting_to_stop = (u < 0.01 and B <= 0.1 and abs(self.v) < 0.1 and abs(self.omega) < 0.5)
        
        if is_braking_to_stop or is_coasting_to_stop:
            self.v = 0.0
            a = 0.0
            self.omega = 0.0
            alpha = 0.0
            F_traction = 0.0
            T_traction = 0.0
            slip_ratio = 0.0
            T_net = 0.0
            F_net = 0.0
            self.is_slipping = False

        self.x += dt * self.v
        self.wheel_angle = (self.wheel_angle + self.omega * dt) % (2.0 * math.pi)
        self._update_load_state(a)

        return [
            self.v, a, self.x, F_traction, F_drag, F_rr, F_net,
            self.omega, alpha, slip_ratio, T_drive, T_brake, T_traction, T_net
        ]


class GraphBuffer:
    """Circular buffer holding the last WINDOW seconds of telemetry per channel."""

    CHANNELS = 14
    WINDOW   = 30.0   # seconds

    def __init__(self, dt):
        self._dt      = dt
        self._max_pts = max(1, int(self.WINDOW / dt) + 10)
        self._bufs    = [collections.deque(maxlen=self._max_pts) for _ in range(self.CHANNELS)]
        self._times   = collections.deque(maxlen=self._max_pts)
        # default (moderate smoothing) for most channels
        self._smoothing_alpha = 0.15
        # stronger smoothing for wheel alpha/slip/torques
        self._strong_smoothing_alpha = 0.05
        self._strong_channels = {8, 9, 10, 11, 13}
        self._ema_values = None
        # Snap very small residual EMA values to zero so channels settle visibly.
        self._ema_zero_epsilon = 1e-3

    def reset(self, new_dt=None):
        if new_dt is not None:
            self._dt      = new_dt
            self._max_pts = max(1, int(self.WINDOW / new_dt) + 10)
            self._bufs    = [collections.deque(maxlen=self._max_pts) for _ in range(self.CHANNELS)]
            self._times   = collections.deque(maxlen=self._max_pts)
        else:
            for b in self._bufs: b.clear()
            self._times.clear()
        self._ema_values = None

    def push(self, t, values):
        self._times.append(t)

        if self._ema_values is None:
            self._ema_values = list(values[:self.CHANNELS])
        else:
            for i in range(min(self.CHANNELS, len(values))):
                if i in (0, 2):
                    self._ema_values[i] = values[i]
                else:
                    alpha = self._strong_smoothing_alpha if i in self._strong_channels else self._smoothing_alpha
                    ema = self._ema_values[i] + alpha * (values[i] - self._ema_values[i])
                    # Prevent long, tiny exponential tails from polluting autoscaled plots.
                    if abs(values[i]) <= self._ema_zero_epsilon and abs(ema) <= self._ema_zero_epsilon:
                        ema = 0.0
                    self._ema_values[i] = ema

        for i, val in enumerate(self._ema_values):
            self._bufs[i].append(val)

    def get(self, channel):
        return list(self._bufs[channel])

    def get_times(self):
        return list(self._times)