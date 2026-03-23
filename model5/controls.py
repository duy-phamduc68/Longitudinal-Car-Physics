# ─────────────────────────────────────────────────────────────────────────────
# controls.py — Xbox controller (XInput) and pygame joystick input handling
# ─────────────────────────────────────────────────────────────────────────────

import sys

try:
    import ctypes
    XINPUT_AVAILABLE = True
except ImportError:
    XINPUT_AVAILABLE = False

# Module-level handle set by load_xinput()
_xinput_dll = None

XINPUT_BUTTON_START = 0x0010  # Xbox Start / Menu button


def load_xinput():
    """Try to load an XInput DLL. Returns True on success."""
    global _xinput_dll
    if not XINPUT_AVAILABLE or sys.platform != "win32":
        return False
    for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            _xinput_dll = ctypes.windll.LoadLibrary(name)
            return True
        except OSError:
            continue
    return False


# ctypes structs are only usable when ctypes imported successfully
if XINPUT_AVAILABLE:
    class XINPUT_GAMEPAD(ctypes.Structure):
        _fields_ = [
            ("wButtons",      ctypes.c_ushort),
            ("bLeftTrigger",  ctypes.c_ubyte),
            ("bRightTrigger", ctypes.c_ubyte),
            ("sThumbLX",      ctypes.c_short),
            ("sThumbLY",      ctypes.c_short),
            ("sThumbRX",      ctypes.c_short),
            ("sThumbRY",      ctypes.c_short),
        ]

    class XINPUT_STATE(ctypes.Structure):
        _fields_ = [
            ("dwPacketNumber", ctypes.c_ulong),
            ("Gamepad",        XINPUT_GAMEPAD),
        ]
else:
    class XINPUT_GAMEPAD:   # noqa: F811  (stub when ctypes unavailable)
        pass

    class XINPUT_STATE:     # noqa: F811
        pass


def get_xinput_state(pad=0):
    """
    Poll XInput pad `pad`.

    Returns (right_trigger_0_to_1, left_trigger_binary, start_button_bool)
    or None if unavailable.
    """
    if _xinput_dll is None:
        return None
    state = XINPUT_STATE()
    ret   = _xinput_dll.XInputGetState(pad, ctypes.byref(state))
    if ret != 0:
        return None

    rt        = state.Gamepad.bRightTrigger / 255.0
    lt        = state.Gamepad.bLeftTrigger / 255.0  # Float for analog brake
    start_btn = bool(state.Gamepad.wButtons & XINPUT_BUTTON_START)
    x_btn     = bool(state.Gamepad.wButtons & 0x4000) # X button
    b_btn_pad = bool(state.Gamepad.wButtons & 0x2000) # B button

    return rt, lt, start_btn, x_btn, b_btn_pad

    return rt, lt, start_btn, x_btn, b_btn_pad