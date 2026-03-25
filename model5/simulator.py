"""
Car Physics Simulator - Model 5 (Slip ratio and dynamic traction curve)
================================
Entry point and main Simulator class.
"""

import pygame
import random

from constants import CONST_FIELDS, THROTTLE_RAMP_DEFAULT, UPSHIFT_RPM, DOWNSHIFT_RPM, PIXELS_PER_METER, TIMESTEP_OPTIONS, FPS_OPTIONS
from physics   import CarModel, GraphBuffer
from controls  import load_xinput, get_xinput_state
from renderer  import (Cloud, draw_sky, draw_clouds, draw_road, draw_car,
                       draw_hud, draw_graph_full, draw_graph_combined, 
                       draw_skid_marks, draw_smoke)
from ui        import OptionsMenu, CheckBox

import os

def _closest_timestep(dt):
    valid_dts = [v for v, _ in TIMESTEP_OPTIONS]
    return min(valid_dts, key=lambda x: abs(x - dt))


def _closest_fps(fps):
    return min(FPS_OPTIONS, key=lambda x: abs(x - fps))


def _load_global_sim_config():
    config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.yaml"))
    dt = 0.01
    target_fps = 60
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                # Strip inline comments after the value, e.g. "fps: 144 # 60 ; ..."
                s = s.split("#", 1)[0].strip()
                if not s:
                    continue
                if s.startswith("timestep:"):
                    try:
                        dt = float(s.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                elif s.startswith("fps:"):
                    try:
                        target_fps = int(float(s.split(":", 1)[1].strip()))
                    except ValueError:
                        pass
    except FileNotFoundError:
        pass

    dt = _closest_timestep(dt)
    target_fps = _closest_fps(target_fps)
    return dt, target_fps


class Simulator:
    SCENE_H_RATIO = 0.52
    GRAPH_H_RATIO = 0.44

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Car Physics Simulator - Model 5")

        self.screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE | pygame.WINDOWMAXIMIZED)
        self.screen_w, self.screen_h = self.screen.get_size()

        self.font_sm = pygame.font.SysFont("Consolas", 13)
        self.font_md = pygame.font.SysFont("Consolas", 17, bold=True)
        self.font_lg = pygame.font.SysFont("Consolas", 22, bold=True)

        self.dt, self.target_fps = _load_global_sim_config()
        self.graph_mode        = "full"
        self.control_mode      = "auto"
        self.throttle_ramp     = THROTTLE_RAMP_DEFAULT
        self.enable_auto_shift = False
        self.show_model2_elements = False
        self.combined_channels = [True] * GraphBuffer.CHANNELS
        self.true_form         = False
        self.day_mode          = False   # false = night (default), true = day
        self.upshift_rpm       = UPSHIFT_RPM
        self.downshift_rpm     = DOWNSHIFT_RPM

        self.car       = CarModel()
        self.graph_buf = GraphBuffer(self.dt)
        self.sim_time  = 0.0
        self.paused    = False

        self.throttle    = 0.0
        self.brake       = 0
        self._drive_throttle = 0.0
        self._drive_brake    = 0.0
        self._w_held     = False
        self._space_held = False
        self._xinput_ok  = load_xinput()
        self._joy        = None
        self._start_prev  = False
        self._select_prev = False
        self._a_prev      = False
        self._x_prev      = False
        self._b_prev      = False
        self._lb_prev     = False
        self._rb_prev     = False
        self._status_message = ""
        self._status_timer = 0.0
        self._init_joystick()

        self._clouds = []
        self._spawn_initial_clouds()
        
        # NEW: Slip Visuals State
        self.skid_marks = []
        self.smoke_particles = []

        self._accumulator = 0.0
        self._clock       = pygame.time.Clock()
        self._fps_display = 0.0
        self._fps_acc     = 0.0
        self._fps_frames  = 0

        self._menu_btn      = pygame.Rect(8, 8, 110, 30)
        self._true_form_cb  = CheckBox(130, 14, "True Form", checked=False)
        self._low_detail_cb = CheckBox(240, 14, "Low Detail", checked=False)
        self.car.low_detail = False
        self.options = OptionsMenu(self)
        self._layout()

    # ── initialisation helpers ────────────────────────────────────────────────
    def _init_joystick(self):
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            self._joy = pygame.joystick.Joystick(0)

    def _layout(self):
        W, H = self.screen_w, self.screen_h
        scene_h = int(H * self.SCENE_H_RATIO)
        self.scene_rect = pygame.Rect(0, 0, W, scene_h)
        road_y = int(scene_h * 0.68)
        self.road_rect = pygame.Rect(0, road_y, W, scene_h - road_y)
        self.road_y = road_y
        self.horizon_y = road_y
        self.graph_rect = pygame.Rect(0, scene_h, W, H - scene_h)
        self.car_cx = W // 2
        self.car_wy = road_y - 2
        self.car_body_w = 180
        self.car_body_h = 52
        self.car_wheel_r = 22

    # ── scenario reset ────────────────────────────────────────────────────────
    def reset_scenario(self):
        saved = {f[1]: getattr(self.car, f[1]) for f in CONST_FIELDS}
        self.car.reset()
        for attr, val in saved.items(): setattr(self.car, attr, val)
        self.graph_buf.reset(new_dt=self.dt)
        self.sim_time = 0.0
        self.throttle = 0.0
        self.brake = 0
        self._drive_throttle = 0.0
        self._drive_brake = 0.0
        self._w_held = False
        self._space_held = False
        self._accumulator = 0.0
        self.skid_marks.clear()
        self.smoke_particles.clear()

    # ── cloud world management ────────────────────────────────────────────────
    def _spawn_initial_clouds(self):
        W = self.screen_w if hasattr(self, 'screen_w') else 1280
        for _ in range(8):
            self._clouds.append(Cloud(random.uniform(-200, W + 200), random.uniform(40, 160), random.uniform(0.6, 1.4)))

    def _ensure_clouds(self, cam_x):
        W = self.screen_w
        while len(self._clouds) < 12:
            self._clouds.append(Cloud(cam_x + W + random.uniform(0, 600), random.uniform(40, int(self.horizon_y * 0.7)), random.uniform(0.6, 1.4)))
        self._clouds = [c for c in self._clouds if c.x > cam_x - 400]
        max_cx = max((c.x for c in self._clouds), default=cam_x)
        while max_cx < cam_x + W + 500:
            max_cx += random.uniform(150, 350)
            self._clouds.append(Cloud(max_cx, random.uniform(40, int(self.horizon_y * 0.7)), random.uniform(0.6, 1.4)))

    # ... [Keep input event handling exactly the same] ...
    def _request_shift(self, delta):
        old_gear = self.car.engine.gear
        max_fwd_gear = max((g for g in self.car.engine.GEAR_RATIOS.keys() if g > 0), default=5)
        new_gear = max(-1, min(max_fwd_gear, old_gear + delta))
        v = self.car.v
        if abs(v) > 0.05 and ((new_gear < 0 and v > 0.0) or (new_gear > 0 and v < 0.0)):
            self._status_message = "Come to a full stop before changing direction"
            self._status_timer = 2.0
            return
        self.car.engine.gear = new_gear

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return False
            if event.type == pygame.VIDEORESIZE:
                self.screen_w, self.screen_h = event.w, event.h
                self._layout()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if not self.options.editing_active:
                    self.options.toggle(); continue
            if event.type == pygame.MOUSEMOTION:
                self._true_form_cb.handle_event(event)
                self._low_detail_cb.handle_event(event)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self.options.visible:
                if self._true_form_cb.handle_event(event):
                    self.true_form = self._true_form_cb.checked; continue
                if self._low_detail_cb.handle_event(event):
                    self.car.low_detail = self._low_detail_cb.checked; continue
            if self.options.handle_event(event): continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._menu_btn.collidepoint(event.pos):
                    self.options.toggle(); continue
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_w, pygame.K_UP): self._w_held = True
                if event.key in (pygame.K_SPACE, pygame.K_DOWN): self._space_held = True
                if event.key in (pygame.K_d, pygame.K_RIGHT) and not self.enable_auto_shift: self._request_shift(+1)
                if event.key in (pygame.K_a, pygame.K_LEFT) and not self.enable_auto_shift: self._request_shift(-1)
                if event.key == pygame.K_1:
                    self.enable_auto_shift = not self.enable_auto_shift
                    st = "ON" if self.enable_auto_shift else "OFF"
                    self._status_message = f"Auto-shift {st}"
                    self._status_timer = 1.5
                if event.key == pygame.K_r:
                    self.reset_scenario()
                    self._status_message = "Scenario reset"
                    self._status_timer = 1.5
            if event.type == pygame.KEYUP:
                if event.key in (pygame.K_w, pygame.K_UP): self._w_held = False
                if event.key in (pygame.K_SPACE, pygame.K_DOWN): self._space_held = False
        return True

    def _update_input(self, dt):
        ctrl_throttle = 0.0; ctrl_brake = 0
        controller_active = False
        xi = get_xinput_state(0)
        if xi is not None:
            rt, lt, *_ = xi
            ctrl_throttle, ctrl_brake = max(0.0, min(1.0, rt)), max(0.0, min(1.0, lt))
            controller_active = (ctrl_throttle > 0.03) or (ctrl_brake > 0.03)
        elif self._joy is not None:
            try:
                rt = (self._joy.get_axis(5) + 1.0) / 2.0
                lt = (self._joy.get_axis(4) + 1.0) / 2.0
                ctrl_throttle, ctrl_brake = max(0.0, min(1.0, rt)), max(0.0, min(1.0, lt))
                controller_active = (ctrl_throttle > 0.03) or (ctrl_brake > 0.03)
            except Exception: pass

        if controller_active:
            self.control_mode = "controller"
            self.throttle, self.brake = round(ctrl_throttle, 3), round(ctrl_brake, 3)
        else:
            self.control_mode = "keyboard"
            rate = 1.0 / max(self.throttle_ramp, 0.001)
            self.throttle = min(1.0, self.throttle + rate * dt) if self._w_held else max(0.0, self.throttle - rate * dt)
            self.brake = min(1.0, self.brake + rate * dt) if self._space_held else max(0.0, self.brake - rate * dt)
            self.throttle, self.brake = round(self.throttle, 3), round(self.brake, 3)

        if self.enable_auto_shift:
            self.car.engine.enable_auto_shift = True
            self.car.engine.upshift_rpm = self.upshift_rpm
            self.car.engine.downshift_rpm = self.downshift_rpm
            self._apply_auto_direction_logic()
        else:
            self.car.engine.enable_auto_shift = False
            self._drive_throttle = self.throttle
            self._drive_brake = self.brake

    def _poll_controller_buttons(self):
        if not self._xinput_ok:
            self._start_prev = self._x_prev = self._b_prev = False; return
        xi = get_xinput_state(0)
        if xi is None:
            self._start_prev = self._x_prev = self._b_prev = self._lb_prev = self._rb_prev = False
            return
        _, _, start_btn, select_btn, a_btn, x_btn, b_btn_pad, lb_btn, rb_btn = xi
        if start_btn and not self._start_prev:
            if not self.options.editing_active: self.options.toggle()
        self._start_prev = start_btn

        if select_btn and not self._select_prev:
            self.reset_scenario()
            self._status_message = "Scenario reset"
            self._status_timer = 1.5

        if a_btn and not self._a_prev:
            self.enable_auto_shift = not self.enable_auto_shift
            st = "ON" if self.enable_auto_shift else "OFF"
            self._status_message = f"Auto-shift {st}"
            self._status_timer = 1.5

        if b_btn_pad and not self._b_prev and not self.enable_auto_shift:
            self._request_shift(+1)
        if x_btn and not self._x_prev and not self.enable_auto_shift:
            self._request_shift(-1)
        if rb_btn and not self._rb_prev and not self.enable_auto_shift:
            self._request_shift(+1)
        if lb_btn and not self._lb_prev and not self.enable_auto_shift:
            self._request_shift(-1)

        self._select_prev, self._a_prev, self._x_prev, self._b_prev, self._lb_prev, self._rb_prev = select_btn, a_btn, x_btn, b_btn_pad, lb_btn, rb_btn

    def _apply_auto_direction_logic(self):
        v, near_stop, throttle_in, brake_in = self.car.v, abs(self.car.v) <= 0.08, self.throttle, self.brake
        if self.car.engine.gear == 0: self.car.engine.gear = 1
        if self.car.engine.gear >= 1:
            if near_stop and brake_in > 0.05 and throttle_in < 0.1:
                self.car.engine.gear = -1
                self._drive_throttle, self._drive_brake = brake_in, 0.0
                return
            self._drive_throttle, self._drive_brake = throttle_in, brake_in
            return
        if brake_in > 0.05:
            self._drive_throttle, self._drive_brake = brake_in, 0.0
            return
        if v < -0.08 and throttle_in > 0.05:
            self._drive_throttle, self._drive_brake = 0.0, throttle_in
            return
        if near_stop and throttle_in > 0.05:
            self.car.engine.gear = 1
            self._drive_throttle, self._drive_brake = throttle_in, 0.0
            return
        self._drive_throttle = self._drive_brake = 0.0


    # ── physics ───────────────────────────────────────────────────────────────

    def _physics_step(self, dt):
        values = self.car.update(dt, self._drive_throttle, self._drive_brake)
        self.sim_time += dt
        self.graph_buf.push(self.sim_time, values)

        # NEW: Slip FX Logic
        if self.car.is_slipping:
            # Rear axle approx world position
            axle_x = self.car.x - (self.car.L / 2)
            slip_ratio = abs(values[9]) if len(values) > 9 else 0.0
            speed = abs(self.car.v)
            intensity = max(0.0, min(1.0, slip_ratio))

            # 1. Update Skid Marks
            if self.skid_marks and self.skid_marks[-1]['alpha'] > 200 and abs(self.skid_marks[-1]['x1'] - axle_x) < 1.0:
                self.skid_marks[-1]['x1'] = axle_x
            else:
                self.skid_marks.append({'x0': axle_x, 'x1': axle_x, 'alpha': 255.0})

            # 2. Spawn Smoke Particles (reduced at low speed; disabled in low-detail mode)
            if not self.car.low_detail:
                smoke_chance = 0.35 if speed < 3.0 else 0.75
                smoke_chance *= 0.4 + 0.6 * intensity
                if random.random() < smoke_chance:
                    self.smoke_particles.append({
                        'x': axle_x,
                        'y': self.road_y - 2,
                        'vx': self.car.v * 0.2 + random.uniform(-0.8, 0.8),
                        'vy': random.uniform(-3, -8) if speed < 2.0 else random.uniform(-5, -15),
                        'r': random.uniform(3, 8) if speed < 2.0 else random.uniform(5, 12),
                        'alpha': 120.0 if speed < 2.0 else 180.0
                    })

        # Update visual fading states
        for s in self.skid_marks: s['alpha'] -= dt * 25.0
        self.skid_marks = [s for s in self.skid_marks if s['alpha'] > 0]

        for p in self.smoke_particles:
            p['x'] += p['vx'] * dt / PIXELS_PER_METER
            p['y'] += p['vy'] * dt
            p['r'] += dt * 15.0
            p['alpha'] -= dt * 60.0
        self.smoke_particles = [p for p in self.smoke_particles if p['alpha'] > 0]


    # ── rendering ─────────────────────────────────────────────────────────────

    def _draw_sky(self, cam_x):
        draw_sky(
            self.screen,
            self.horizon_y,
            self.screen_w,
            cam_x,
            low_detail=self.car.low_detail,
            day_mode=self.day_mode,
        )

    def _draw_clouds(self, cam_x):
        if not self.car.low_detail:
            self._ensure_clouds(cam_x * 0.3)
            draw_clouds(self.screen, self._clouds, cam_x, self.screen_w)
    
    def _draw_road(self, cam_x):
        draw_road(self.screen, self.road_rect, self.road_y, self.screen_w, cam_x, self.font_sm)
        # NEW: Draw the VFX
        draw_skid_marks(self.screen, self.skid_marks, self.road_y, self.screen_w, cam_x)
        draw_smoke(self.screen, self.smoke_particles, self.screen_w, cam_x)

    def _draw_car(self):
        draw_car(self.screen, self.car_cx, self.car_wy, self.car_body_w, self.car_body_h, self.car_wheel_r,
                 self.true_form, self.car, self.font_sm, self.graph_rect.y, self.show_model2_elements)

    def _draw_hud(self):
        status_message = self._status_message if self._status_timer > 0.0 else None
        draw_hud(self.screen, self.font_sm, self.font_lg, self._menu_btn, self._true_form_cb,
                 self._low_detail_cb, self._fps_display,
                 self.sim_time, self.car, self.throttle, self.brake, self.paused, self.horizon_y, self.screen_w,
                 self.dt, self.target_fps, status_message, self.enable_auto_shift)

    def _draw_graph_area(self):
        self.graph_buf.car_gear = self.car.engine.gear
        self.graph_buf.car_ref = self.car
        if self.graph_mode == "full": draw_graph_full(self.screen, self.graph_rect, self.graph_buf, self.font_sm)
        else: draw_graph_combined(self.screen, self.graph_rect, self.graph_buf, self.font_sm, self.combined_channels)

    # ── main loop ─────────────────────────────────────────────────────────────

    def run(self):
        running = True
        while running:
            frame_dt_ms = self._clock.tick(self.target_fps)
            frame_dt    = min(frame_dt_ms / 1000.0, 0.1)

            if self._status_timer > 0.0: self._status_timer = max(0.0, self._status_timer - frame_dt)

            self._fps_acc    += frame_dt
            self._fps_frames += 1
            if self._fps_acc >= 0.5:
                self._fps_display = self._fps_frames / self._fps_acc
                self._fps_acc     = 0.0
                self._fps_frames  = 0

            if (self.screen.get_width()  != self.screen_w or self.screen.get_height() != self.screen_h):
                self.screen_w = self.screen.get_width()
                self.screen_h = self.screen.get_height()
                self._layout()

            running     = self._handle_events()
            self._poll_controller_buttons()
            self.paused = self.options.visible

            if not self.paused:
                self._update_input(frame_dt)
                self._accumulator += frame_dt
                _max_steps = max(1, int(0.05 / self.dt))
                _steps = 0
                while self._accumulator >= self.dt and _steps < _max_steps:
                    self._physics_step(self.dt)
                    self._accumulator -= self.dt
                    _steps += 1

            cam_x = self.car.x
            self._draw_sky(cam_x)
            self._draw_clouds(cam_x)
            self._draw_road(cam_x)
            self._draw_car()
            self._draw_graph_area()
            self._draw_hud()
            self.options.draw(self.screen, self.font_sm, self.font_md)

            pygame.display.flip()

        pygame.quit()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sim = Simulator()
    sim.run()