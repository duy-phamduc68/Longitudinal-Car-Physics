# ─────────────────────────────────────────────────────────────────────────────
# constants.py — All named constants for the Car Physics Simulator
# ─────────────────────────────────────────────────────────────────────────────

# ── Physics defaults ──────────────────────────────────────────────────────────
M         = 1500    # kg
I_W       = 3.0     # kg·m^2 (Rotational Inertia of Drive Wheels)
C_RR      = 13.0    # rolling resistance coefficient
C_DRAG    = 0.43    # aerodynamic drag coefficient
C_BRAKE_TORQUE = 4500.0 # N·m (Max clamping torque of brakes)
MU        = 1.0     # tire friction coefficient placeholder
g         = 9.81    # m/s^2
L         = 2.8     # m  wheelbase
h         = 0.5     # m  CG height above axle line
b         = 1.7     # m  CG -> front axle
c         = 1.1     # m  CG -> rear axle

PIXELS_PER_METER = 100   # 1 m = 100 px
MARKER_INTERVAL  = 25    # metres between road markers

# —— Drivetrain constants (Model 4) —————————————————————————————————
R_W         = 0.33    # m (wheel radius)
FINAL_DRIVE = 3.42    # differential ratio
ETA         = 0.7     # drivetrain efficiency

GEAR_RATIOS = {
    -1: 3.166, # Reverse
     0: 0.0,   # Neutral
     1: 2.97,
     2: 2.07,
     3: 1.43,
     4: 1.00,
     5: 0.84,
}

RPM_IDLE    = 800
RPM_REDLINE = 6000
UPSHIFT_RPM = 5200
DOWNSHIFT_RPM = 2200

TORQUE_CURVE = [
    (800,  200),
    (1000, 250),
    (2000, 320),
    (3000, 380),
    (4000, 400),
    (5000, 380),
    (6000, 300),
]

def get_max_torque(rpm, curve=None):
    use_curve = curve if curve is not None else TORQUE_CURVE
    if not use_curve:
        return 0.0
    if rpm <= use_curve[0][0]:
        return use_curve[0][1]
    if rpm >= use_curve[-1][0]:
        return use_curve[-1][1]
    for i in range(len(use_curve) - 1):
        r1, t1 = use_curve[i]
        r2, t2 = use_curve[i + 1]
        if r1 <= rpm <= r2:
            t = (rpm - r1) / (r2 - r1)
            return t1 + t * (t2 - t1)
    return 0.0


def parse_gear_ratios(text):
    """
    Parse gear-ratio text into {-1,0,1,2,3,4,5} dict.

    Input format examples:
      "R:3.2, N:0, 1:2.9, 2:2.0, 3:1.4, 4:1.0, 5:0.8"
      "-1:3.2, 0:0, 1:2.9, 2:2.0, 3:1.4, 4:1.0, 5:0.8"
    """
    if text is None:
        raise ValueError("Gear ratio text is empty")

    out = {}
    tokens = [tok.strip() for tok in str(text).split(",") if tok.strip()]
    for tok in tokens:
        if ":" not in tok:
            raise ValueError(f"Invalid gear ratio token: {tok}")
        key_raw, val_raw = [p.strip() for p in tok.split(":", 1)]
        key_norm = key_raw.upper()
        if key_norm == "R":
            key = -1
        elif key_norm == "N":
            key = 0
        else:
            key = int(float(key_raw))
        if key not in (-1, 0, 1, 2, 3, 4, 5):
            raise ValueError(f"Unsupported gear key: {key_raw}")
        val = float(val_raw)
        if key == 0:
            val = 0.0
        elif val <= 0.0:
            raise ValueError("Non-neutral gear ratio must be > 0")
        out[key] = val

    required = {-1, 0, 1, 2, 3, 4, 5}
    if set(out.keys()) != required:
        missing = sorted(required - set(out.keys()))
        raise ValueError(f"Missing gear keys: {missing}")
    return out


def gear_ratios_to_str(ratios):
    if ratios is None:
        ratios = GEAR_RATIOS
    order = [(-1, "R"), (0, "N"), (1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5")]
    parts = []
    for key, label in order:
        val = float(ratios.get(key, 0.0))
        parts.append(f"{label}:{val:g}")
    return ", ".join(parts)


def parse_torque_curve(text):
    """
    Parse torque curve text to sorted list of (rpm, torque) tuples.

    Format:
      "1000:120, 2000:180, 3000:220"
    """
    if text is None:
        raise ValueError("Torque curve text is empty")

    points = []
    tokens = [tok.strip() for tok in str(text).split(",") if tok.strip()]
    for tok in tokens:
        if ":" not in tok:
            raise ValueError(f"Invalid torque token: {tok}")
        rpm_raw, tq_raw = [p.strip() for p in tok.split(":", 1)]
        rpm = float(rpm_raw)
        tq = float(tq_raw)
        if rpm <= 0:
            raise ValueError("RPM must be > 0")
        if tq < 0:
            raise ValueError("Torque must be >= 0")
        points.append((rpm, tq))

    if len(points) < 2:
        raise ValueError("Torque curve needs at least 2 points")

    points.sort(key=lambda p: p[0])
    dedup = []
    last_rpm = None
    for rpm, tq in points:
        if last_rpm is not None and abs(rpm - last_rpm) < 1e-9:
            dedup[-1] = (rpm, tq)
        else:
            dedup.append((rpm, tq))
            last_rpm = rpm
    if len(dedup) < 2:
        raise ValueError("Torque curve has duplicate RPM points only")
    return dedup


def torque_curve_to_str(curve):
    if curve is None:
        curve = TORQUE_CURVE
    return ", ".join(f"{rpm:g}:{torque:g}" for rpm, torque in curve)


# ── Colour palette ────────────────────────────────────────────────────────────
SKY_TOP        = (8, 18, 46)
SKY_BOTTOM     = (135, 0, 181)
ROAD_COLOR     = (50,  50,  50)
ROAD_LINE      = (200, 200, 200)
MARKER_COLOR   = (255, 255, 255)
CAR_BODY       = (230, 110,  20)
CAR_ROOF       = (200,  80,  10)
CAR_WINDOW     = (170, 210, 255)
CAR_WHEEL      = (30,   30,  30)
CAR_WHEEL_RIM  = (140, 140, 140)
CLOUD_COLOR    = (255, 255, 255)
GRAPH_BG       = (20,  20,  28)
GRAPH_GRID     = (50,  50,  60)
GRAPH_AXIS     = (120, 120, 130)
OVERLAY_BG     = (15,  15,  20, 210)
PANEL_BG       = (25,  28,  38, 240)
TEXT_BRIGHT    = (230, 235, 255)
TEXT_DIM       = (140, 145, 165)
ACCENT         = (224, 42, 255)
ACCENT2        = (255, 140,  50)
BTN_NORMAL     = (45,  50,  68)
BTN_HOVER      = (65,  72,  96)
BTN_ACTIVE     = (155, 105, 186)

GRAPH_COLORS = [
    (100, 220, 100),   # 0: velocity      - green
    (255, 180,  60),   # 1: acceleration  - orange
    ( 80, 180, 255),   # 2: position      - blue
    (255, 100, 100),   # 3: F_traction* - red
    (180, 100, 255),   # 4: F_drag        - purple
    (255, 220,  80),   # 5: F_rr          - yellow
    (200, 200, 200),   # 6: Net Force     - white/grey
    
    (100, 255, 200),   # 7: Wheel w       - cyan
    (255, 200,  80),   # 8: Wheel alpha   - gold
    (100, 100, 100),   # 9: Slip Ratio    - GRAYED OUT
    (255, 100, 100),   # 10: T_drive      - red
    (255,  80, 140),   # 11: T_brake      - pink
    (180, 100, 255),   # 12: T_traction* - purple
    (200, 200, 200),   # 13: Net Torque* - white/grey
]

GRAPH_LABELS = [
    "Velocity (m/s)",
    "Accel (m/s²)",
    "Position (m)",
    "F_traction* (N)",
    "Drag Force (N)",
    "Rolling Res. (N)",
    "Net Force (N)",
    "Wheel \u03C9 (rad/s)",
    "Wheel \u03B1 (rad/s²)",
    "Slip Ratio \u03C3 (INACTIVE)", 
    "Drive Torque (N·m)",
    "Brake Torque (N·m)",
    "T_traction* (N·m)",
    "Net Torque* (N·m)",
]

# ── Simulation option tables ──────────────────────────────────────────────────
TIMESTEP_OPTIONS = [
    (0.001,  "1 ms  - High Fidelity"),
    (0.01,   "10 ms - Good"),
    (0.016,  "16 ms - 60 Hz"),
    (0.1,    "100 ms - Low Precision"),
]

FPS_OPTIONS = [30, 60, 120, 144, 240]

THROTTLE_RAMP_DEFAULT = 1.0   # seconds to go 0→1

# ── Physics constants field table ─────────────────────────────────────────────
# Each entry: (display_name, CarModel_attr, unit_hint, default_value)
CONST_FIELDS = [
    ("Mass", "M", "kg", M),
    ("Wheelbase", "L", "m", L),
    ("CG Height", "h", "m", h),
    ("b", "b", "m", b),
    ("c", "c", "m", c),
    ("Rolling Resistance", "C_RR", "coef", C_RR),
    ("Aerodynamic Drag", "C_DRAG", "coef", C_DRAG),
    ("Brake Torque", "C_BRAKE_TORQUE", "N·m", C_BRAKE_TORQUE),
    
    ("Final Drive Ratio", "FINAL_DRIVE", "ratio", FINAL_DRIVE),
    ("Wheel Radius", "R_W", "m", R_W),
    ("Wheel Inertia", "I_W", "kg·m²", I_W),
    ("Drivetrain Efficiency", "ETA", "0-1", ETA),
    ("RPM Idle", "RPM_IDLE", "rpm", RPM_IDLE),
    ("RPM Redline", "RPM_REDLINE", "rpm", RPM_REDLINE),
    ("Gear Ratios", "GEAR_RATIOS", "R,N,1-5", GEAR_RATIOS),
    ("Torque Curve", "TORQUE_CURVE", "rpm:Nm", TORQUE_CURVE),
]


CONST_SECTIONS = [
    (
        "Drivetrain",
        [
            ("Gear Ratios", "GEAR_RATIOS", "R,N,1-5", GEAR_RATIOS),
            ("Final Drive Ratio", "FINAL_DRIVE", "ratio", FINAL_DRIVE),
            ("Wheel Radius", "R_W", "m", R_W),
            ("Wheel Inertia", "I_W", "kg·m²", I_W),
            ("Drivetrain Efficiency", "ETA", "0-1", ETA),
        ],
    ),
    (
        "Engine",
        [
            ("RPM Idle", "RPM_IDLE", "rpm", RPM_IDLE),
            ("RPM Redline", "RPM_REDLINE", "rpm", RPM_REDLINE),
            ("Torque Curve", "TORQUE_CURVE", "rpm:Nm", TORQUE_CURVE),
        ],
    ),
    (
        "Vehicle Geometry & Mass",
        [
            ("Mass", "M", "kg", M),
            ("Wheelbase", "L", "m", L),
            ("CG Height", "h", "m", h),
            ("b", "b", "m", b),
            ("c", "c", "m", c),
        ],
    ),
    (
        "Resistances",
        [
            ("Rolling Resistance", "C_RR", "coef", C_RR),
            ("Aerodynamic Drag", "C_DRAG", "coef", C_DRAG),
            ("Brake Torque", "C_BRAKE_TORQUE", "N·m", C_BRAKE_TORQUE),
        ],
    ),
    (
        "Tires / Traction",
        [
            # MU is not editable in UI, so not included here
        ],
    ),
]


# ── Editable parameter limits ─────────────────────────────────────────────────
PARAM_LIMITS = {
    "g": (5.0, 15.0),
    "L": (2.0, 4.5),
    "h": (0.2, 1.2),
    "b": (0.5, 3.0),
    "c": (0.5, 3.0),
    "M": (500.0, 5000.0),
    "I_W": (0.1, 50.0),           # Added Wheel Inertia
    "C_RR": (0.0, 80.0),
    "C_DRAG": (0.0, 2.5),
    "C_BRAKE_TORQUE": (1000.0, 30000.0),
    "FINAL_DRIVE": (1.0, 8.0),
    "R_W": (0.15, 0.6),
    "ETA": (0.3, 1.0),
    "RPM_IDLE": (500.0, 2000.0),
    "RPM_REDLINE": (2000.0, 12000.0),
}
