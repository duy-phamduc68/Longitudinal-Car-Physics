# ─────────────────────────────────────────────────────────────────────────────
# constants.py — All named constants for the Car Physics Simulator
# ─────────────────────────────────────────────────────────────────────────────

# ── Physics defaults ──────────────────────────────────────────────────────────
M         = 1500    # kg
I_W       = 3.0     # kg·m^2 (Rotational Inertia of Drive Wheels)
C_RR      = 13.0    # rolling resistance coefficient
C_DRAG    = 0.43    # aerodynamic drag coefficient
C_BRAKE_TORQUE = 4500.0 # N·m (Max clamping torque of brakes)
MU        = 1.0     # tire friction coefficient
C_T       = 30000.0 # N/slip (Traction stiffness)
g         = 9.81    # m/s^2
L         = 2.8     # m  wheelbase
h         = 0.5     # m  CG height above axle line
b         = 1.7     # m  CG -> front axle
c         = 1.1     # m  CG -> rear axle

PIXELS_PER_METER = 100   # 1 m = 100 px
MARKER_INTERVAL  = 25    # metres between road markers

# —— Drivetrain constants —————————————————————————————————
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
    if text is None: raise ValueError("Gear ratio text is empty")
    out = {}
    tokens = [tok.strip() for tok in str(text).split(",") if tok.strip()]
    for tok in tokens:
        if ":" not in tok: raise ValueError(f"Invalid gear ratio token: {tok}")
        key_raw, val_raw = [p.strip() for p in tok.split(":", 1)]
        key_norm = key_raw.upper()
        if key_norm == "R": key = -1
        elif key_norm == "N": key = 0
        else: key = int(float(key_raw))
        if key not in (-1, 0, 1, 2, 3, 4, 5): raise ValueError(f"Unsupported gear key: {key_raw}")
        val = float(val_raw)
        if key == 0: val = 0.0
        elif val <= 0.0: raise ValueError("Non-neutral gear ratio must be > 0")
        out[key] = val
    required = {-1, 0, 1, 2, 3, 4, 5}
    if set(out.keys()) != required:
        missing = sorted(required - set(out.keys()))
        raise ValueError(f"Missing gear keys: {missing}")
    return out

def gear_ratios_to_str(ratios):
    if ratios is None: ratios = GEAR_RATIOS
    order = [(-1, "R"), (0, "N"), (1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5")]
    parts = []
    for key, label in order:
        val = float(ratios.get(key, 0.0))
        parts.append(f"{label}:{val:g}")
    return ", ".join(parts)

def parse_torque_curve(text):
    if text is None: raise ValueError("Torque curve text is empty")
    points = []
    tokens = [tok.strip() for tok in str(text).split(",") if tok.strip()]
    for tok in tokens:
        if ":" not in tok: raise ValueError(f"Invalid torque token: {tok}")
        rpm_raw, tq_raw = [p.strip() for p in tok.split(":", 1)]
        rpm, tq = float(rpm_raw), float(tq_raw)
        if rpm <= 0: raise ValueError("RPM must be > 0")
        if tq < 0: raise ValueError("Torque must be >= 0")
        points.append((rpm, tq))
    if len(points) < 2: raise ValueError("Torque curve needs at least 2 points")
    points.sort(key=lambda p: p[0])
    dedup = []
    last_rpm = None
    for rpm, tq in points:
        if last_rpm is not None and abs(rpm - last_rpm) < 1e-9: dedup[-1] = (rpm, tq)
        else:
            dedup.append((rpm, tq))
            last_rpm = rpm
    if len(dedup) < 2: raise ValueError("Torque curve has duplicate RPM points only")
    return dedup

def torque_curve_to_str(curve):
    if curve is None: curve = TORQUE_CURVE
    return ", ".join(f"{rpm:g}:{torque:g}" for rpm, torque in curve)

# ── Colour palette ────────────────────────────────────────────────────────────
SKY_TOP        = (8, 18, 46)
SKY_BOTTOM     = (135, 0, 181)
ROAD_COLOR     = (50,  50,  50)
ROAD_LINE      = (200, 200, 200)
MARKER_COLOR   = (255, 255, 255)
CAR_BODY       = (40, 40,  40)
CAR_ROOF       = (200,  80,  10)
CAR_WINDOW     = (46, 144, 255)
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
    (255, 100, 100),   # 3: F_traction    - red
    (180, 100, 255),   # 4: F_drag        - purple
    (255, 220,  80),   # 5: F_rr          - yellow
    (200, 200, 200),   # 6: Net Force     - white/grey
    (100, 255, 200),   # 7: Wheel w       - cyan
    (255, 200,  80),   # 8: Wheel alpha   - gold
    (255,  80, 255),   # 9: Slip Ratio    - hot pink
    (255, 100, 100),   # 10: T_drive      - red
    (255,  80, 140),   # 11: T_brake      - pink
    (180, 100, 255),   # 12: T_traction   - purple
    (200, 200, 200),   # 13: Net Torque   - white/grey
]

GRAPH_LABELS = [
    "Velocity (m/s)",
    "Accel (m/s²)",
    "Position (m)",
    "F_traction (N)",
    "Drag Force (N)",
    "Rolling Res. (N)",
    "Net Force (N)",
    "Wheel \u03C9 (rad/s)",
    "Wheel \u03B1 (rad/s²)",
    "Slip Ratio \u03C3", 
    "Drive Torque (N·m)",
    "Brake Torque (N·m)",
    "T_traction (N·m)",
    "Net Torque (N·m)",
]

# ── Simulation option tables ──────────────────────────────────────────────────
TIMESTEP_OPTIONS = [
    (0.001,  "1 ms  - High Fidelity"),
    (0.01,   "10 ms - Good"),
    (0.016,  "16 ms - 60 Hz"),
    (0.1,    "100 ms - Low Precision"),
]
FPS_OPTIONS = [30, 60, 120, 144, 240]
THROTTLE_RAMP_DEFAULT = 1.0

# ── Physics constants field table ─────────────────────────────────────────────
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
    ("Tire Friction (\u03BC)", "MU", "coef", MU),
    ("Traction Stiffness", "C_T", "N/slip", C_T),
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
            ("Tire Friction (\u03BC)", "MU", "coef", MU),
            ("Traction Stiffness", "C_T", "N/slip", C_T),
        ],
    ),
]

PARAM_LIMITS = {
    "g": (5.0, 15.0),
    "L": (2.0, 4.5),
    "h": (0.2, 1.2),
    "b": (0.5, 3.0),
    "c": (0.5, 3.0),
    "M": (500.0, 5000.0),
    "I_W": (0.1, 50.0),
    "C_RR": (0.0, 80.0),
    "C_DRAG": (0.0, 2.5),
    "C_BRAKE_TORQUE": (1000.0, 30000.0),
    "FINAL_DRIVE": (1.0, 8.0),
    "R_W": (0.15, 0.6),
    "ETA": (0.3, 1.0),
    "RPM_IDLE": (500.0, 2000.0),
    "RPM_REDLINE": (2000.0, 12000.0),
    "MU": (0.1, 5.0),
    "C_T": (1000.0, 500000.0),
}

# ─────────────────────────────────────────────────────────────
# VEHICLE PRESETS
# ─────────────────────────────────────────────────────────────

# ── 1. Economy Compact (e.g. small city car) ─────────────────
ECONOMY_COMPACT = {
    "M": 1100,
    "I_W": 2.0,
    "C_RR": 10.0,
    "CHASSIS_COLOR": (255, 255, 255),
    "C_DRAG": 0.32,
    "C_BRAKE_TORQUE": 3500.0,
    "MU": 0.9,
    "C_T": 20000.0,

    "R_W": 0.30,
    "FINAL_DRIVE": 3.9,
    "ETA": 0.85,

    "RPM_IDLE": 800,
    "RPM_REDLINE": 6500,
    "UPSHIFT_RPM": 5000,
    "DOWNSHIFT_RPM": 2000,

    "GEAR_RATIOS": {
        -1: 3.4, 0: 0.0,
        1: 3.5, 2: 2.1, 3: 1.4, 4: 1.0, 5: 0.8,
    },

    "TORQUE_CURVE": [
        (800,  90),
        (1500, 120),
        (2500, 140),
        (3500, 150),
        (4500, 145),
        (5500, 130),
        (6500, 100),
    ],
}


# ── 2. Sports Car (NA / balanced performance) ────────────────
SPORTS_CAR = {
    "M": 1400,
    "I_W": 2.5,
    "CHASSIS_COLOR": (230, 110,  20),
    "C_RR": 12.0,
    "C_DRAG": 0.38,
    "C_BRAKE_TORQUE": 6000.0,
    "MU": 1.2,
    "C_T": 45000.0,

    "R_W": 0.33,
    "FINAL_DRIVE": 3.6,
    "ETA": 0.9,

    "RPM_IDLE": 900,
    "RPM_REDLINE": 7500,
    "UPSHIFT_RPM": 6800,
    "DOWNSHIFT_RPM": 3000,

    "GEAR_RATIOS": {
        -1: 3.2, 0: 0.0,
        1: 3.1, 2: 2.2, 3: 1.6, 4: 1.2, 5: 1.0,
    },

    "TORQUE_CURVE": [
        (1000, 180),
        (2000, 240),
        (3000, 300),
        (4000, 340),
        (5000, 360),
        (6500, 350),
        (7500, 300),
    ],
}


# ── 3. Turbo Performance Car (high torque spike) ─────────────
TURBO_PERFORMANCE = {
    "M": 1550,
    "I_W": 3.0,
    "CHASSIS_COLOR": (245, 46, 46),
    "C_RR": 13.0,
    "C_DRAG": 0.42,
    "C_BRAKE_TORQUE": 7000.0,
    "MU": 1.3,
    "C_T": 60000.0,

    "R_W": 0.34,
    "FINAL_DRIVE": 3.2,
    "ETA": 0.88,

    "RPM_IDLE": 900,
    "RPM_REDLINE": 7000,
    "UPSHIFT_RPM": 6500,
    "DOWNSHIFT_RPM": 2500,

    "GEAR_RATIOS": {
        -1: 3.1, 0: 0.0,
        1: 2.9, 2: 2.1, 3: 1.5, 4: 1.2, 5: 1.0,
    },

    "TORQUE_CURVE": [
        (1000, 200),
        (2000, 350),
        (3000, 450),
        (4000, 500),
        (5000, 480),
        (6000, 420),
        (7000, 350),
    ],
}


# ── 4. Heavy SUV / Pickup ────────────────────────────────────
SUV_TRUCK = {
    "M": 2400,
    "I_W": 4.5,
    "CHASSIS_COLOR": (90, 90, 158),
    "C_RR": 18.0,
    "C_DRAG": 0.55,
    "C_BRAKE_TORQUE": 9000.0,
    "MU": 1.0,
    "C_T": 35000.0,

    "R_W": 0.38,
    "FINAL_DRIVE": 3.9,
    "ETA": 0.8,

    "RPM_IDLE": 700,
    "RPM_REDLINE": 5500,
    "UPSHIFT_RPM": 4500,
    "DOWNSHIFT_RPM": 1500,

    "GEAR_RATIOS": {
        -1: 3.5, 0: 0.0,
        1: 3.8, 2: 2.4, 3: 1.6, 4: 1.2, 5: 0.9,
    },

    "TORQUE_CURVE": [
        (800, 250),
        (1500, 350),
        (2500, 420),
        (3500, 450),
        (4500, 430),
        (5500, 380),
    ],
}


# ── 5. Electric Vehicle (single-speed) ───────────────────────
ELECTRIC_EV = {
    "M": 1800,
    "I_W": 2.8,
    "CHASSIS_COLOR": (131, 227, 227),
    "C_RR": 12.0,
    "C_DRAG": 0.28,
    "C_BRAKE_TORQUE": 8000.0,
    "MU": 1.3,
    "C_T": 80000.0,

    "R_W": 0.34,
    "FINAL_DRIVE": 9.0,   # EV reduction gear
    "ETA": 0.95,

    "RPM_IDLE": 0,
    "RPM_REDLINE": 16000,
    "UPSHIFT_RPM": 16000,
    "DOWNSHIFT_RPM": 0,

    "GEAR_RATIOS": {
        -1: 1.0, 0: 0.0,
        1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0,
    },

    "TORQUE_CURVE": [
        (0,     400),
        (2000,  400),
        (6000,  380),
        (10000, 300),
        (14000, 200),
        (16000, 150),
    ],
}

DEFAULT_PRESET = {
    "M": M,
    "I_W": I_W,
    "CHASSIS_COLOR": CAR_BODY,
    "C_RR": C_RR,
    "C_DRAG": C_DRAG,
    "C_BRAKE_TORQUE": C_BRAKE_TORQUE,
    "MU": MU,
    "C_T": C_T,
    "R_W": R_W,
    "FINAL_DRIVE": FINAL_DRIVE,
    "ETA": ETA,
    "RPM_IDLE": RPM_IDLE,
    "RPM_REDLINE": RPM_REDLINE,
    "UPSHIFT_RPM": UPSHIFT_RPM,
    "DOWNSHIFT_RPM": DOWNSHIFT_RPM,
    "GEAR_RATIOS": dict(GEAR_RATIOS),
    "TORQUE_CURVE": list(TORQUE_CURVE),
}
