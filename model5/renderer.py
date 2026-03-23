# ─────────────────────────────────────────────────────────────────────────────
# renderer.py — All pygame drawing: scene, car, HUD, graphs, clouds
# ─────────────────────────────────────────────────────────────────────────────

import math
import pygame
import random

from constants import (
    SKY_TOP, SKY_BOTTOM,
    ROAD_COLOR, MARKER_COLOR,
    CAR_BODY, CAR_ROOF, CAR_WINDOW, CAR_WHEEL, CAR_WHEEL_RIM,
    CLOUD_COLOR,
    GRAPH_BG, GRAPH_GRID, GRAPH_AXIS,
    PANEL_BG, ACCENT,
    TEXT_BRIGHT, TEXT_DIM,
    BTN_NORMAL, BTN_HOVER,
    GRAPH_COLORS, GRAPH_LABELS,
    PIXELS_PER_METER, MARKER_INTERVAL,
)
from physics import GraphBuffer


# ─────────────────────────────────────────────────────────────────────────────
# Module-level render caches
# ─────────────────────────────────────────────────────────────────────────────

_sky_cache: dict = {}          # keyed by (horizon_y, screen_w)
_marker_label_cache: dict = {} # keyed by distance in metres
_star_cache: dict = {}         # keyed by (horizon_y, screen_w)


# ─────────────────────────────────────────────────────────────────────────────
# Cloud entity
# ─────────────────────────────────────────────────────────────────────────────

class Cloud:
    def __init__(self, x, y, scale):
        self.x     = float(x)
        self.y     = float(y)
        self.scale = scale   # 0.5 - 1.5

    def draw(self, surface, draw_x=None):
        s = self.scale
        cx = int(draw_x if draw_x is not None else self.x)
        cy = int(self.y)
        circles = [
            (cx,               cy,               int(28*s)),
            (cx + int(24*s),   cy - int(10*s),   int(22*s)),
            (cx - int(22*s),   cy - int(8*s),    int(20*s)),
            (cx + int(8*s),    cy - int(18*s),   int(18*s)),
        ]
        for rx, ry, rr in circles:
            pygame.draw.circle(surface, CLOUD_COLOR, (rx, ry), rr)


# ─────────────────────────────────────────────────────────────────────────────
# Scene drawing
# ─────────────────────────────────────────────────────────────────────────────

def draw_sky(surface, horizon_y, screen_w, cam_x=0.0):
    """Draw a vertical gradient midnight sky and a slow-parallax star layer."""
    key = (horizon_y, screen_w)
    if key not in _sky_cache:
        sky_surf = pygame.Surface((screen_w, horizon_y))
        for y in range(horizon_y):
            t = y / max(horizon_y, 1)
            r = int(SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * t)
            g = int(SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * t)
            b = int(SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * t)
            pygame.draw.line(sky_surf, (r, g, b), (0, y), (screen_w, y))
        _sky_cache.clear()   # keep only the most-recent size
        _sky_cache[key] = sky_surf

    if key not in _star_cache:
        rng = random.Random(screen_w * 10007 + horizon_y * 97)
        span = screen_w * 3
        star_count = max(120, screen_w // 6)
        stars = []
        for _ in range(star_count):
            stars.append(
                (
                    rng.uniform(0, span),
                    rng.uniform(6, max(8, horizon_y - 24)),
                    rng.randint(1, 2),
                    rng.randint(180, 255),
                )
            )
        _star_cache.clear()
        _star_cache[key] = (span, stars)

    surface.blit(_sky_cache[key], (0, 0))

    span, stars = _star_cache[key]
    parallax_offset = cam_x * 0.08
    for sx, sy, sr, sa in stars:
        x = int((sx - parallax_offset) % span) - screen_w
        if 0 <= x < screen_w:
            pygame.draw.circle(surface, (sa, sa, sa), (x, int(sy)), sr)


def draw_clouds(surface, clouds, cam_x, screen_w):
    """Render world-space clouds at parallax speed (30% of car speed)."""
    parallax_offset = cam_x * 0.3
    for c in clouds:
        screen_x = c.x - parallax_offset
        if -200 < screen_x < screen_w + 200:
            c.draw(surface, screen_x)


def draw_road(surface, road_rect, road_y, screen_w, cam_x, font_sm):
    """Draw road fill, dashed centre line, and distance markers."""
    pygame.draw.rect(surface, ROAD_COLOR, road_rect)

    # Dashed centre line
    dash_len   = 60
    gap_len    = 50
    period     = dash_len + gap_len
    road_mid_y = road_y + road_rect.height // 3
    offset_px  = int(cam_x * PIXELS_PER_METER) % period
    x = -offset_px
    while x < screen_w + period:
        pygame.draw.rect(surface, (120, 120, 120),
                         (x, road_mid_y - 2, dash_len, 4))
        x += period

    # Distance markers every MARKER_INTERVAL metres
    cam_px         = cam_x * PIXELS_PER_METER
    first_marker_m = math.floor(cam_x / MARKER_INTERVAL) * MARKER_INTERVAL
    m = first_marker_m
    while True:
        world_px = m * PIXELS_PER_METER
        screen_x = int(world_px - cam_px + screen_w // 2)
        if screen_x > screen_w + 10:
            break
        if screen_x < -10:
            m += MARKER_INTERVAL
            continue
        pygame.draw.line(surface, MARKER_COLOR,
                         (screen_x, road_y),
                         (screen_x, road_y + 14), 2)
        lbl = _marker_label_cache.get(m)
        if lbl is None:
            lbl = font_sm.render(f"{m}m", True, MARKER_COLOR)
            _marker_label_cache[m] = lbl
        surface.blit(lbl, (screen_x - lbl.get_width() // 2, road_y + 16))
        m += MARKER_INTERVAL


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _mix_color(c0, c1, t):
    t = _clamp(t, 0.0, 1.0)
    return (
        int(c0[0] + (c1[0] - c0[0]) * t),
        int(c0[1] + (c1[1] - c0[1]) * t),
        int(c0[2] + (c1[2] - c0[2]) * t),
    )


def _load_color(load, static_load):
    if static_load <= 1e-6:
        return (255, 255, 255)
    if load >= static_load:
        t = (load - static_load) / (0.45 * static_load)
        return _mix_color((255, 255, 255), (255, 70, 70), t)
    t = (static_load - load) / (0.45 * static_load)
    return _mix_color((255, 255, 255), (80, 220, 80), t)


def _draw_vertical_arrow(surface, x, y_base, length, color):
    tip_y = int(y_base - length)
    pygame.draw.line(surface, color, (x, y_base), (x, tip_y), 3)
    pygame.draw.polygon(surface, color, [
        (x, tip_y - 8),
        (x - 7, tip_y + 6),
        (x + 7, tip_y + 6),
    ])


def _draw_transfer_bar(surface, center_x, y, width, height, dW, W, font_sm):
    bar_rect = pygame.Rect(center_x - width // 2, y, width, height)
    pygame.draw.rect(surface, (24, 24, 34), bar_rect, border_radius=6)
    pygame.draw.rect(surface, (170, 170, 180), bar_rect, 1, border_radius=6)

    center_x_px = bar_rect.centerx
    max_shift = (width // 2) - 8
    ratio = 0.0 if W <= 1e-6 else _clamp(dW / W, -0.20, 0.20)
    shift = int((ratio / 0.20) * max_shift) if max_shift > 0 else 0

    if shift > 0:
        fill = pygame.Rect(center_x_px, y + 2, shift, height - 4)
        pygame.draw.rect(surface, _mix_color((255, 190, 190), (255, 70, 70), shift / max_shift), fill)
    elif shift < 0:
        fill = pygame.Rect(center_x_px + shift, y + 2, -shift, height - 4)
        pygame.draw.rect(surface, _mix_color((190, 210, 255), (70, 130, 255), -shift / max_shift), fill)

    pygame.draw.line(surface, (230, 230, 235), (center_x_px, y - 3), (center_x_px, y + height + 3), 2)
    pygame.draw.line(surface, (255, 255, 255), (center_x_px + shift, y - 4), (center_x_px + shift, y + height + 4), 2)

    title = font_sm.render("[ Front Transfer ] | [ Rear Transfer ]", True, (225, 225, 235))
    surface.blit(title, title.get_rect(center=(center_x, y - 14)))

    pct = 0.0 if W <= 1e-6 else (dW / W) * 100.0
    if pct > 0:
        msg = f"+{pct:.1f}% rear transfer"
        col = (255, 110, 110)
    elif pct < 0:
        msg = f"{pct:.1f}% front transfer"
        col = (110, 160, 255)
    else:
        msg = "0.0% transfer"
        col = (245, 245, 245)
    lbl = font_sm.render(msg, True, col)
    surface.blit(lbl, lbl.get_rect(center=(center_x, y + height + 12)))


def draw_wheel(surface, cx, cy, r, angle):
    """Draw a wheel with spokes so rotation is clearly visible."""
    pygame.draw.circle(surface, CAR_WHEEL, (cx, cy), r)
    pygame.draw.circle(surface, (190, 190, 190), (cx, cy), r, 2)
    for i in range(4):
        a = angle + i * (math.pi / 2.0)
        x = cx + int(math.cos(a) * r * 0.8)
        y = cy + int(math.sin(a) * r * 0.8)
        pygame.draw.line(surface, CAR_WHEEL_RIM, (cx, cy), (x, y), max(2, r // 8))
    pygame.draw.circle(surface, CAR_WHEEL_RIM, (cx, cy), max(3, r // 6))


def draw_car(surface, cx, wy, body_w, body_h, wheel_r,
             true_form=False, car=None, font_sm=None, road_bottom_y=None,
             show_model2_elements=True):
    """Draw a simple geometric car centred at (cx, wy).

    When true_form is True draw a rigid-body load transfer diagram using
    wheelbase/CG geometry from the physics model.
    """
    if car is None:
        return

    wheel_scale = 1.02
    wheel_r = max(12, int(max(0.0, car.engine.R_W) * PIXELS_PER_METER * wheel_scale))

    font_sm = font_sm or pygame.font.SysFont("Consolas", 13)

    def _bar_y(default_y):
        if road_bottom_y is None:
            return default_y
        return int(road_bottom_y - 36)

    if true_form:
        axle_y = wy - wheel_r
        wheelbase_px = max(160, int(car.L * PIXELS_PER_METER))
        rear_x = int(cx - wheelbase_px / 2)
        front_x = int(cx + wheelbase_px / 2)
        cg_ratio = 0.5 if car.L <= 1e-6 else _clamp(car.c / car.L, 0.0, 1.0)
        cg_x = int(rear_x + wheelbase_px * cg_ratio)
        cg_y = int(axle_y - car.h * PIXELS_PER_METER)

        pygame.draw.line(surface, (220, 220, 220), (front_x, axle_y), (rear_x, axle_y), 3)

        for wx in (front_x, rear_x):
            draw_wheel(surface, wx, axle_y, wheel_r, car.wheel_angle)

        body_y = axle_y - 46
        pygame.draw.line(surface, (200, 200, 205), (front_x, body_y), (rear_x, body_y), 4)
        pygame.draw.line(surface, (180, 180, 190), (cg_x, axle_y), (cg_x, cg_y), 2)
        pygame.draw.circle(surface, (255, 245, 120), (cg_x, cg_y), 6)

        _draw_vertical_arrow(surface, cg_x, cg_y + 2, 46, (245, 245, 245))
        w_lbl = font_sm.render("W = M g", True, (235, 235, 240))
        surface.blit(w_lbl, (cg_x + 10, cg_y - 52))

        mid_y = int((axle_y + cg_y) / 2)
        pygame.draw.line(surface, (140, 160, 200), (cg_x + 24, axle_y), (cg_x + 24, cg_y), 1)
        h_lbl = font_sm.render(f"h={car.h:.2f}m", True, (150, 175, 220))
        surface.blit(h_lbl, (cg_x + 28, mid_y - 8))

        dim_y = axle_y + 34
        pygame.draw.line(surface, (145, 145, 155), (front_x, dim_y), (rear_x, dim_y), 1)
        l_lbl = font_sm.render(f"L={car.L:.2f}m", True, (210, 210, 220))
        surface.blit(l_lbl, l_lbl.get_rect(center=(cx, dim_y + 10)))

        top_dim_y = axle_y - 20
        pygame.draw.line(surface, (145, 145, 155), (rear_x, top_dim_y), (cg_x, top_dim_y), 1)
        pygame.draw.line(surface, (145, 145, 155), (cg_x, top_dim_y), (front_x, top_dim_y), 1)

        b_lbl = font_sm.render(f"b={car.b:.2f}", True, (200, 200, 210))
        c_lbl = font_sm.render(f"c={car.c:.2f}", True, (200, 200, 210))

        surface.blit(c_lbl, c_lbl.get_rect(center=((rear_x + cg_x) // 2, top_dim_y - 10)))
        surface.blit(b_lbl, b_lbl.get_rect(center=((cg_x + front_x) // 2, top_dim_y - 10)))

        if show_model2_elements:
            wf_len = _clamp(20 + (car.Wf / max(car.Wf_static, 1.0)) * 38, 14, 92)
            wr_len = _clamp(20 + (car.Wr / max(car.Wr_static, 1.0)) * 38, 14, 92)

            wf_col = _load_color(car.Wf, car.Wf_static)
            wr_col = _load_color(car.Wr, car.Wr_static)

            _draw_vertical_arrow(surface, front_x, axle_y - 2, wf_len, wf_col)
            _draw_vertical_arrow(surface, rear_x, axle_y - 2, wr_len, wr_col)

            wf_lbl = font_sm.render(f"Wf={car.Wf:.0f}N", True, wf_col)
            wr_lbl = font_sm.render(f"Wr={car.Wr:.0f}N", True, wr_col)

            surface.blit(wf_lbl, wf_lbl.get_rect(center=(front_x, axle_y + wheel_r + 16)))
            surface.blit(wr_lbl, wr_lbl.get_rect(center=(rear_x, axle_y + wheel_r + 16)))

            _draw_transfer_bar(surface, cx, _bar_y(axle_y + wheel_r + 44), 260, 16,
                               car.dW, car.W, font_sm)
        return

    # --- simplified sprite mode ---

    axle_y = wy - wheel_r
    wheelbase_px = max(140, int(car.L * PIXELS_PER_METER))

    rear_x = int(cx - wheelbase_px / 2)
    front_x = int(cx + wheelbase_px / 2)

    cg_ratio = 0.5 if car.L <= 1e-6 else _clamp(car.c / car.L, 0.0, 1.0)
    cg_x = int(rear_x + wheelbase_px * cg_ratio)
    cg_y = int(axle_y - car.h * PIXELS_PER_METER)

    body_bottom = int(axle_y - wheel_r + 18)
    body_top = int(body_bottom - max(32, 0.20 * wheelbase_px))

    x0 = rear_x - 6
    x1 = rear_x + int(0.20 * wheelbase_px)
    x2 = rear_x + int(0.42 * wheelbase_px)
    x3 = rear_x + int(0.65 * wheelbase_px)
    x4 = front_x - int(0.14 * wheelbase_px)
    x5 = front_x + 6

    y0 = body_bottom
    y1 = body_top + 14
    y2 = body_top
    y3 = body_top
    y4 = body_top + 18

    car_shape = [
        (x0, y0),
        (x0, y1),
        (x1, y2),
        (x3, y3),
        (x4, y4),
        (x5, y4),
        (x5, y0),
    ]

    pygame.draw.polygon(surface, CAR_BODY, car_shape)
    pygame.draw.polygon(surface, (0, 0, 0), car_shape, 2)

    # window
    win_w = int((x5 - x0) * 0.28)
    win_h = int((y0 - y2) * 0.35)

    win_rect = pygame.Rect(
        cx - win_w // 2,
        y2 + 6,
        win_w,
        win_h
    )

    pygame.draw.rect(surface, CAR_WINDOW, win_rect, border_radius=4)

    # wheels
    for wx in (rear_x, front_x):
        draw_wheel(surface, wx, axle_y, wheel_r, car.wheel_angle)

    if show_model2_elements:
        pygame.draw.line(surface, (220, 220, 225), (rear_x, axle_y), (front_x, axle_y), 2)
    # pygame.draw.circle(surface, (255, 245, 120), (cg_x, cg_y), 5)

    if show_model2_elements:
        wf_len = _clamp(16 + (car.Wf / max(car.Wf_static, 1.0)) * 24, 12, 56)
        wr_len = _clamp(16 + (car.Wr / max(car.Wr_static, 1.0)) * 24, 12, 56)

        wf_col = _load_color(car.Wf, car.Wf_static)
        wr_col = _load_color(car.Wr, car.Wr_static)

        _draw_vertical_arrow(surface, front_x, axle_y - wheel_r - 4, wf_len, wf_col)
        _draw_vertical_arrow(surface, rear_x, axle_y - wheel_r - 4, wr_len, wr_col)

        wf_lbl = font_sm.render(f"Wf={car.Wf:.0f}", True, wf_col)
        wr_lbl = font_sm.render(f"Wr={car.Wr:.0f}", True, wr_col)

        surface.blit(wf_lbl, wf_lbl.get_rect(center=(front_x, axle_y + wheel_r + 14)))
        surface.blit(wr_lbl, wr_lbl.get_rect(center=(rear_x, axle_y + wheel_r + 14)))

        _draw_transfer_bar(surface, cx, _bar_y(axle_y + wheel_r + 44), 220, 14,
                           car.dW, car.W, font_sm)


def draw_dashboard(surface, font_sm, car, throttle, brake, screen_w, horizon_y, auto_shift_on=False):
    dash_w = 200
    dash_h = 130
    dash_x = screen_w - dash_w - 20
    dash_y = horizon_y - dash_h - 20
    
    panel = pygame.Rect(dash_x, dash_y, dash_w, dash_h)
    pygame.draw.rect(surface, (30, 30, 30, 200), panel, border_radius=8)
    pygame.draw.rect(surface, (100, 100, 100), panel, 1, border_radius=8)

    engine = getattr(car, "engine", car)
    rpm_idle = float(getattr(engine, "RPM_IDLE", 800.0))
    rpm_redline = float(getattr(engine, "RPM_REDLINE", 6000.0))
    if rpm_redline <= rpm_idle:
        rpm_redline = rpm_idle + 1.0
    
    # Gear
    g_str = 'R' if engine.gear == -1 else ('N' if engine.gear == 0 else str(engine.gear))
    g_lbl = font_sm.render(f"Gear: {g_str}", True, (255, 255, 255))
    surface.blit(g_lbl, (dash_x + 10, dash_y + 10))

    mode_str = "AUTO" if auto_shift_on else "MANUAL"
    mode_col = (255, 210, 90) if auto_shift_on else (190, 190, 190)
    m_lbl = font_sm.render(f"Shift: {mode_str}", True, mode_col)
    surface.blit(m_lbl, (dash_x + 88, dash_y + 10))
    
    # RPM bar
    rpm_pct = max(0.0, min(1.0, (engine.rpm - rpm_idle) / (rpm_redline - rpm_idle)))
    pygame.draw.rect(surface, (50, 50, 50), (dash_x + 10, dash_y + 35, 180, 10))
    pygame.draw.rect(surface, (200, 50, 50) if rpm_pct > 0.9 else (50, 200, 50), 
                     (dash_x + 10, dash_y + 35, int(180 * rpm_pct), 10))
    r_lbl = font_sm.render(f"RPM: {int(engine.rpm)}", True, (200, 200, 200))
    surface.blit(r_lbl, (dash_x + 10, dash_y + 48))
    
    # Throttle gauge
    t_rect = pygame.Rect(dash_x + 10, dash_y + 80, int(80 * throttle), 8)
    pygame.draw.rect(surface, (50, 50, 50), (dash_x + 10, dash_y + 80, 80, 8))
    if throttle > 0: pygame.draw.rect(surface, (100, 200, 100), t_rect)
    surface.blit(font_sm.render("THR", True, (150, 150, 150)), (dash_x + 10, dash_y + 90))
    
    # Brake gauge
    b_rect = pygame.Rect(dash_x + 110, dash_y + 80, int(80 * brake), 8)
    pygame.draw.rect(surface, (50, 50, 50), (dash_x + 110, dash_y + 80, 80, 8))
    if brake > 0: pygame.draw.rect(surface, (200, 100, 100), b_rect)
    surface.blit(font_sm.render("BRK", True, (150, 150, 150)), (dash_x + 110, dash_y + 90))

def draw_hud(surface, font_sm, font_lg, menu_btn, true_form_cb,
             fps_display, sim_time, car, throttle, brake,
             paused, horizon_y, screen_w,
             dt, target_fps,
             status_message=None,
             auto_shift_on=False):
    """Draw the HUD: options button, True Form checkbox, FPS, telemetry stats, paused banner."""
    # Menu button
    hover = menu_btn.collidepoint(pygame.mouse.get_pos())
    pygame.draw.rect(surface, BTN_HOVER if hover else BTN_NORMAL,
                     menu_btn, border_radius=5)
    pygame.draw.rect(surface, ACCENT, menu_btn, 1, border_radius=5)
    lbl = font_sm.render("Options", True, TEXT_BRIGHT)
    surface.blit(lbl, lbl.get_rect(center=menu_btn.center))

    # True Form checkbox (immediately right of the Options button)
    top_text_col = (227, 42, 255)
    true_form_cb.draw(surface, font_sm, text_color=top_text_col)

    # Telemetry stats (top-centre)
    top_shadow_col = (70, 45, 10)

    # FPS + sim configuration (top-right)
    fps_lines = [
        f"FPS: {fps_display:.0f}",
        f"dt: {dt:.3f}s | target: {target_fps}",
    ]
    for i, line in enumerate(fps_lines):
        txt = font_sm.render(line, True, top_text_col)
        shd = font_sm.render(line, True, top_shadow_col)
        x = screen_w - txt.get_width() - 8
        y = 8 + i * 17
        surface.blit(shd, (x + 1, y + 1))
        surface.blit(txt, (x, y))

    stats = [
        f"t = {sim_time:06.2f} s",
        f"v = {car.v:.2f} m/s  ({car.v * 3.6:.1f} km/h)",
        f"x = {car.x:.1f} m",
        f"T = {throttle:.2f}   B = {brake:.2f}",
    ]
    for i, s in enumerate(stats):
        t = font_sm.render(s, True, top_text_col)
        tx = screen_w // 2 - t.get_width() // 2
        ty = 8 + i * 17
        shadow = font_sm.render(s, True, top_shadow_col)
        surface.blit(shadow, (tx + 1, ty + 1))
        surface.blit(t, (tx, ty))

    if status_message:
        warn_col = (255, 198, 40)
        warn_shadow_col = (60, 36, 8)
        msg = font_sm.render(status_message, True, warn_col)
        msg_shadow = font_sm.render(status_message, True, warn_shadow_col)
        msg_rect = msg.get_rect(center=(screen_w // 2, 84))
        surface.blit(msg_shadow, (msg_rect.x + 1, msg_rect.y + 1))
        surface.blit(msg, msg_rect)

    # Paused banner
    if paused:
        pb = font_lg.render("── PAUSED (Options open) ──", True, (255, 220, 60))
        surface.blit(pb, pb.get_rect(centerx=screen_w // 2, y=horizon_y - 36))
    draw_dashboard(surface, font_sm, car, throttle, brake, screen_w, horizon_y, auto_shift_on)


# ─────────────────────────────────────────────────────────────────────────────
# Graph renderers
# ─────────────────────────────────────────────────────────────────────────────

def _downsample(data: list, max_pts: int) -> list:
    """
    Return at most max_pts elements from data using Peak-Preservation.
    This prevents thin spikes from flickering/jittering as they scroll.
    """
    n = len(data)
    if n <= max_pts:
        return data
        
    res = []
    step = n / max_pts
    for i in range(max_pts):
        start = int(i * step)
        end = int((i + 1) * step)
        
        chunk = data[start:end] if end > start else [data[start]]
        
        # Find the most extreme values in this chunk of time
        c_min = min(chunk)
        c_max = max(chunk)
        c_first = chunk[0]
        
        # Keep the value that deviates the most from the start of the chunk
        if abs(c_max - c_first) > abs(c_min - c_first):
            res.append(c_max)
        else:
            res.append(c_min)
            
    return res


def draw_graph_full(surface, rect, graph_buf, font_sm):
    """Draw 14 individual channel plots in a strict 2 rows x 7 columns grid."""
    n_cols = 7
    n_rows = 2
    w_each = rect.width // n_cols
    h_each = rect.height // n_rows
    margin = 4

    pygame.draw.rect(surface, GRAPH_BG, rect)

    for ch in range(GraphBuffer.CHANNELS):
        # Calculate exactly which row and column this channel belongs to
        col = ch % n_cols
        row = ch // n_cols
        
        r = pygame.Rect(rect.x + col * w_each + margin,
                        rect.y + row * h_each + margin,
                        w_each - 2 * margin,
                        h_each - 2 * margin)
        
        # "Grayed Out" logic for Slip Ratio (Channel 9)
        is_grayed = (ch == 9)
        bg_col = (15, 15, 18) if is_grayed else GRAPH_BG
        grid_col = (30, 30, 35) if is_grayed else GRAPH_GRID
        text_col = (90, 90, 100) if is_grayed else GRAPH_COLORS[ch]

        pygame.draw.rect(surface, bg_col, r)
        pygame.draw.rect(surface, grid_col, r, 1)

        data = graph_buf.get(ch)
        if len(data) < 2:
            lbl = font_sm.render(GRAPH_LABELS[ch], True, text_col)
            surface.blit(lbl, (r.x + 4, r.y + 4))
            continue
            
        data = _downsample(data, max(2, r.width))

        mn, mx = min(data), max(data)
        if mx == mn:
            mid = (mn + mx) / 2
            mn  = mid - 1.0
            mx  = mid + 1.0

        # Horizontal grid lines and Y-axis labels
        for gi in range(5):
            gy = r.bottom - int((gi / 4) * r.height)
            pygame.draw.line(surface, grid_col, (r.x, gy), (r.right, gy))
            if not is_grayed:
                val_lbl = font_sm.render(f"{mn + (mx - mn) * (gi / 4):.1f}", True, (100, 100, 110))
                surface.blit(val_lbl, (r.x + 2, gy - 9))

        # Plot the curve
        pts = []
        for i, v in enumerate(data):
            px_ = r.x + int(i / (len(data) - 1) * r.width)
            py_ = r.bottom - int((v - mn) / (mx - mn) * r.height)
            py_ = max(r.y, min(r.bottom, py_))
            pts.append((px_, py_))
            
        if len(pts) >= 2:
            pygame.draw.lines(surface, text_col, False, pts, 2)

        # Title Label
        lbl = font_sm.render(GRAPH_LABELS[ch], True, text_col)
        surface.blit(lbl, (r.x + 4, r.y + 4))



def draw_graph_combined(surface, rect, graph_buf, font_sm, channels_active):
    """Draw all active channels normalized 0→1 on a single plot."""
    pygame.draw.rect(surface, GRAPH_BG,   rect)
    pygame.draw.rect(surface, GRAPH_GRID, rect, 1)

    r = rect.inflate(-8, -8)

    # Grid
    for gi in range(5):
        gy = r.bottom - int((gi / 4) * r.height)
        pygame.draw.line(surface, GRAPH_GRID, (r.x, gy), (r.right, gy))
        val_lbl = font_sm.render(f"{gi / 4:.2f}", True, GRAPH_AXIS)
        surface.blit(val_lbl, (r.x + 2, gy - 9))

    legend_x = rect.x + 8
    legend_y = rect.y + 10

    for ch in range(GraphBuffer.CHANNELS):
        if not channels_active[ch]:
            continue
        data = graph_buf.get(ch)
        if len(data) < 2:
            continue
        data = _downsample(data, max(2, r.width))
        mn, mx = min(data), max(data)
        if mx == mn:
            mn -= 1.0
            mx += 1.0

        pts = []
        for i, v in enumerate(data):
            px_  = r.x + int(i / (len(data) - 1) * r.width)
            norm = (v - mn) / (mx - mn)
            py_  = r.bottom - int(norm * r.height)
            py_  = max(r.y, min(r.bottom, py_))
            pts.append((px_, py_))
        if len(pts) >= 2:
            pygame.draw.lines(surface, GRAPH_COLORS[ch], False, pts, 2)

        # Legend swatch + label
        pygame.draw.line(surface, GRAPH_COLORS[ch],
                         (legend_x, legend_y + 6),
                         (legend_x + 18, legend_y + 6), 2)
        lbl = font_sm.render(GRAPH_LABELS[ch], True, GRAPH_COLORS[ch])
        surface.blit(lbl, (legend_x + 22, legend_y))
        legend_x += lbl.get_width() + 36
        if legend_x > rect.right - 120:
            legend_x  = rect.x + 8
            legend_y += 18

    note = font_sm.render("Normalized 0.0 → 1.0 per channel", True, TEXT_DIM)
    surface.blit(note, (rect.x + rect.width - note.get_width() - 8,
                        rect.bottom - note.get_height() - 4))
