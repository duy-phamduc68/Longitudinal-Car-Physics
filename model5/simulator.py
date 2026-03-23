"""
Car Physics Simulator - Model 4 (wheel rotation dynamics)
================================
Entry point and main Simulator class.  All domain logic lives in the
sibling modules:

    engine.py     - drivetrain / engine model (RPM, gears, torque, wheel force)
    constants.py  - named constants (physics defaults, colours, option tables)
    physics.py    - CarModel, GraphBuffer
    controls.py   - XInput / pygame-joystick input handling
    renderer.py   - Cloud entity, scene + graph drawing functions
    ui.py         - Button, CheckBox, OptionsMenu widgets
"""

import pygame
import random

from constants import CONST_FIELDS, THROTTLE_RAMP_DEFAULT, UPSHIFT_RPM, DOWNSHIFT_RPM
from physics   import CarModel, GraphBuffer
from controls  import load_xinput, get_xinput_state
from renderer  import (Cloud, draw_sky, draw_clouds, draw_road, draw_car,
                       draw_hud, draw_graph_full, draw_graph_combined)
from ui        import OptionsMenu, CheckBox


# ─────────────────────────────────────────────────────────────────────────────
# MAIN SIMULATOR
# ─────────────────────────────────────────────────────────────────────────────

class Simulator:
    SCENE_H_RATIO = 0.52   # fraction of window height for the scene
    GRAPH_H_RATIO = 0.44   # fraction for the graph strip

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Car Physics Simulator - Model 4")

        # Initialize with a fallback resolution, then flag it to maximize and allow resizing
        self.screen = pygame.display.set_mode(
            (1280, 720), pygame.RESIZABLE | pygame.WINDOWMAXIMIZED)
        
        # Grab the actual maximized dimensions the OS assigned
        self.screen_w, self.screen_h = self.screen.get_size()

        # Fonts
        self.font_sm = pygame.font.SysFont("Consolas", 13)
        self.font_md = pygame.font.SysFont("Consolas", 17, bold=True)
        self.font_lg = pygame.font.SysFont("Consolas", 22, bold=True)

        # Simulation settings
        self.dt                = 0.01
        self.target_fps        = 60
        self.graph_mode        = "full"
        self.control_mode      = "auto"
        self.throttle_ramp     = THROTTLE_RAMP_DEFAULT
        self.enable_auto_shift = False
        self.show_model2_elements = False
        self.combined_channels = [True] * GraphBuffer.CHANNELS
        self.true_form         = False
        self.upshift_rpm       = UPSHIFT_RPM
        self.downshift_rpm     = DOWNSHIFT_RPM

        # Physics state
        self.car       = CarModel()
        self.graph_buf = GraphBuffer(self.dt)
        self.sim_time  = 0.0
        self.paused    = False

        # Input state
        self.throttle    = 0.0
        self.brake       = 0
        self._drive_throttle = 0.0
        self._drive_brake    = 0.0
        self._w_held     = False
        self._space_held = False
        self._xinput_ok  = load_xinput()
        self._joy        = None
        self._start_prev = False   # XInput Start edge-detection
        self._x_prev     = False
        self._b_prev     = False
        self._status_message = ""
        self._status_timer = 0.0
        self._init_joystick()

        # Clouds (stored in world-space x coordinates)
        self._clouds = []
        self._spawn_initial_clouds()

        # Fixed-timestep accumulator
        self._accumulator = 0.0

        # FPS tracking
        self._clock       = pygame.time.Clock()
        self._fps_display = 0.0
        self._fps_acc     = 0.0
        self._fps_frames  = 0

        # HUD menu button + True Form checkbox
        self._menu_btn      = pygame.Rect(8, 8, 110, 30)
        # Vertically centred with the 30-px menu button, 12 px gap to its right
        self._true_form_cb  = CheckBox(130, 14, "True Form", checked=False)

        # Options overlay
        self.options = OptionsMenu(self)

        # Recompute layout rects
        self._layout()

    # ── initialisation helpers ────────────────────────────────────────────────

    def _init_joystick(self):
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            self._joy = pygame.joystick.Joystick(0)
            self._joy.init()

    def _layout(self):
        W, H    = self.screen_w, self.screen_h
        scene_h = int(H * self.SCENE_H_RATIO)

        self.scene_rect = pygame.Rect(0, 0, W, scene_h)

        road_y         = int(scene_h * 0.68)
        self.road_rect = pygame.Rect(0, road_y, W, scene_h - road_y)
        self.road_y    = road_y
        self.horizon_y = road_y

        self.graph_rect = pygame.Rect(0, scene_h, W, H - scene_h)

        self.car_cx     = W // 2
        self.car_wy     = road_y - 2
        self.car_body_w = 180
        self.car_body_h = 52
        self.car_wheel_r = 22

    # ── scenario reset ────────────────────────────────────────────────────────

    def reset_scenario(self):
        """Reset kinematic state while preserving current physics constants."""
        saved = {f[1]: getattr(self.car, f[1]) for f in CONST_FIELDS}
        self.car.reset()
        for attr, val in saved.items():
            setattr(self.car, attr, val)
        self.graph_buf.reset(new_dt=self.dt)
        self.sim_time     = 0.0
        self.throttle     = 0.0
        self.brake        = 0
        self._drive_throttle = 0.0
        self._drive_brake    = 0.0
        self._w_held      = False
        self._space_held  = False
        self._accumulator = 0.0

    # ── cloud world management ────────────────────────────────────────────────

    def _spawn_initial_clouds(self):
        W = self.screen_w if hasattr(self, 'screen_w') else 1280
        for _ in range(8):
            self._clouds.append(Cloud(
                random.uniform(-200, W + 200),
                random.uniform(40, 160),
                random.uniform(0.6, 1.4),
            ))

    def _ensure_clouds(self, cam_x):
        """Maintain an infinite cloud field around the current camera position."""
        W = self.screen_w

        while len(self._clouds) < 12:
            self._clouds.append(Cloud(
                cam_x + W + random.uniform(0, 600),
                random.uniform(40, int(self.horizon_y * 0.7)),
                random.uniform(0.6, 1.4),
            ))

        self._clouds = [c for c in self._clouds if c.x > cam_x - 400]

        max_cx = max((c.x for c in self._clouds), default=cam_x)
        while max_cx < cam_x + W + 500:
            max_cx += random.uniform(150, 350)
            self._clouds.append(Cloud(
                max_cx,
                random.uniform(40, int(self.horizon_y * 0.7)),
                random.uniform(0.6, 1.4),
            ))

    # ── event / input handling ────────────────────────────────────────────────

    def _request_shift(self, delta):
        old_gear = self.car.engine.gear
        max_fwd_gear = max((g for g in self.car.engine.GEAR_RATIOS.keys() if g > 0), default=5)
        new_gear = max(-1, min(max_fwd_gear, old_gear + delta))

        v = self.car.v

        # Direction changes (forward<->reverse) require a full stop.
        if abs(v) > 0.05 and ((new_gear < 0 and v > 0.0) or (new_gear > 0 and v < 0.0)):
            self._status_message = "Come to a full stop before changing direction"
            self._status_timer = 2.0
            return

        self.car.engine.gear = new_gear

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.VIDEORESIZE:
                self.screen_w, self.screen_h = event.w, event.h
                self._layout()

            # ESC toggles the options menu (unless a text field is being edited)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if not self.options.editing_active:
                    self.options.toggle()
                    continue

            # True Form checkbox – always track hover; block clicks when options open
            if event.type == pygame.MOUSEMOTION:
                self._true_form_cb.handle_event(event)
            if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                    and not self.options.visible):
                if self._true_form_cb.handle_event(event):
                    self.true_form = self._true_form_cb.checked
                    continue

            if self.options.handle_event(event):
                continue

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._menu_btn.collidepoint(event.pos):
                    self.options.toggle()
                    continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_w:
                    self._w_held = True
                if event.key == pygame.K_SPACE:
                    self._space_held = True
                if event.key == pygame.K_d and not self.enable_auto_shift:
                    self._request_shift(+1)
                if event.key == pygame.K_a and not self.enable_auto_shift:
                    self._request_shift(-1)
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_w:
                    self._w_held = False
                if event.key == pygame.K_SPACE:
                    self._space_held = False

        return True

    def _update_input(self, dt):
        ctrl_throttle = 0.0
        ctrl_brake = 0
        controller_active = False

        xi = get_xinput_state(0)
        if xi is not None:
            rt, lt, _ , _, _ = xi   # start_btn handled by _poll_controller_buttons
            ctrl_throttle = max(0.0, min(1.0, rt))
            ctrl_brake = max(0.0, min(1.0, lt))
            controller_active = (ctrl_throttle > 0.03) or (ctrl_brake > 0.03)
        elif self._joy is not None:
            try:
                rt = (self._joy.get_axis(5) + 1.0) / 2.0
                ctrl_throttle = max(0.0, min(1.0, rt))
                lt = (self._joy.get_axis(4) + 1.0) / 2.0
                ctrl_brake = max(0.0, min(1.0, lt))
                controller_active = (ctrl_throttle > 0.03) or (ctrl_brake > 0.03)
            except Exception:
                pass

        if controller_active:
            self.control_mode = "controller"
            self.throttle = round(ctrl_throttle, 3)
            self.brake = round(ctrl_brake, 3)
        else:
            # Keyboard fallback when controller is neutral/disconnected.
            self.control_mode = "keyboard"
            rate = 1.0 / max(self.throttle_ramp, 0.001)
            if self._w_held:
                self.throttle = min(1.0, self.throttle + rate * dt)
            else:
                self.throttle = max(0.0, self.throttle - rate * dt)

            # Upgrade brake to analog feel for consistency
            if self._space_held:
                self.brake = min(1.0, self.brake + rate * dt)
            else:
                self.brake = max(0.0, self.brake - rate * dt)

            self.throttle = round(self.throttle, 3)
            self.brake = round(self.brake, 3)

        if self.enable_auto_shift:
            self.car.engine.enable_auto_shift = True
            self.car.engine.upshift_rpm = self.upshift_rpm
            self.car.engine.downshift_rpm = self.downshift_rpm
            self._apply_auto_direction_logic()
        else:
            self.car.engine.enable_auto_shift = False
            self._drive_throttle = self.throttle
            self._drive_brake = self.brake

    # ── controller menu shortcut ──────────────────────────────────────────────


    def _poll_controller_buttons(self):
        """Toggle options when Xbox Start is newly pressed (edge-detect)."""
        if not self._xinput_ok:
            self._start_prev = False
            self._x_prev = False
            self._b_prev = False
            return
        xi = get_xinput_state(0)
        if xi is None:
            self._start_prev = False
            self._x_prev = False
            self._b_prev = False
            return
        _, _, start_btn, x_btn, b_btn_pad = xi
        if start_btn and not self._start_prev:
            if not self.options.editing_active:
                self.options.toggle()
        self._start_prev = start_btn
        
        if b_btn_pad and not self._b_prev and not self.enable_auto_shift:
            self._request_shift(+1)
        if x_btn and not self._x_prev and not self.enable_auto_shift:
            self._request_shift(-1)
        self._x_prev = x_btn
        self._b_prev = b_btn_pad

    def _apply_auto_direction_logic(self):
        """Auto mode unifies reverse control onto brake input and enforces full-stop direction changes."""
        v = self.car.v
        near_stop = abs(v) <= 0.08
        throttle_in = self.throttle
        brake_in = self.brake

        if self.car.engine.gear == 0:
            self.car.engine.gear = 1

        # Forward gear behavior.
        if self.car.engine.gear >= 1:
            if near_stop and brake_in > 0.05 and throttle_in < 0.1:
                self.car.engine.gear = -1
                self._drive_throttle = brake_in
                self._drive_brake = 0.0
                return

            self._drive_throttle = throttle_in
            self._drive_brake = brake_in
            return

        # Reverse gear behavior: brake input doubles as reverse throttle.
        if brake_in > 0.05:
            self._drive_throttle = brake_in
            self._drive_brake = 0.0
            return

        # Forward throttle while reversing should brake first, not flip direction instantly.
        if v < -0.08 and throttle_in > 0.05:
            self._drive_throttle = 0.0
            self._drive_brake = throttle_in
            return

        if near_stop and throttle_in > 0.05:
            self.car.engine.gear = 1
            self._drive_throttle = throttle_in
            self._drive_brake = 0.0
            return

        self._drive_throttle = 0.0
        self._drive_brake = 0.0


    # ── physics ───────────────────────────────────────────────────────────────

    def _physics_step(self, dt):
            values = self.car.update(dt, self._drive_throttle, self._drive_brake)
            self.sim_time += dt
            self.graph_buf.push(self.sim_time, values)

    # ── rendering (thin wrappers delegating to renderer module) ───────────────

    def _draw_sky(self, cam_x):
        draw_sky(self.screen, self.horizon_y, self.screen_w, cam_x)

    def _draw_clouds(self, cam_x):
        self._ensure_clouds(cam_x * 0.3)
        draw_clouds(self.screen, self._clouds, cam_x, self.screen_w)

    def _draw_road(self, cam_x):
        draw_road(self.screen, self.road_rect, self.road_y,
                  self.screen_w, cam_x, self.font_sm)

    def _draw_car(self):
        draw_car(self.screen,
                 self.car_cx, self.car_wy,
                 self.car_body_w, self.car_body_h, self.car_wheel_r,
                 self.true_form, self.car, self.font_sm,
                 self.graph_rect.y,
                 self.show_model2_elements)

    def _draw_hud(self):
        status_message = self._status_message if self._status_timer > 0.0 else None
        draw_hud(self.screen, self.font_sm, self.font_lg,
                 self._menu_btn, self._true_form_cb, self._fps_display,
                 self.sim_time, self.car,
                 self.throttle, self.brake,
                 self.paused, self.horizon_y, self.screen_w,
                 self.dt, self.target_fps,
                 status_message,
                 self.enable_auto_shift)

    def _draw_graph_area(self):
        self.graph_buf.car_gear = self.car.engine.gear
        self.graph_buf.car_ref = self.car
        if self.graph_mode == "full":
            draw_graph_full(self.screen, self.graph_rect,
                            self.graph_buf, self.font_sm)
        else:
            draw_graph_combined(self.screen, self.graph_rect,
                                self.graph_buf, self.font_sm,
                                self.combined_channels)

    # ── main loop ─────────────────────────────────────────────────────────────

    def run(self):
        running = True
        while running:
            frame_dt_ms = self._clock.tick(self.target_fps)
            frame_dt    = min(frame_dt_ms / 1000.0, 0.1)

            if self._status_timer > 0.0:
                self._status_timer = max(0.0, self._status_timer - frame_dt)

            # FPS counter
            self._fps_acc    += frame_dt
            self._fps_frames += 1
            if self._fps_acc >= 0.5:
                self._fps_display = self._fps_frames / self._fps_acc
                self._fps_acc     = 0.0
                self._fps_frames  = 0

            # Handle window resize (fullscreen guard)
            if (self.screen.get_width()  != self.screen_w or
                    self.screen.get_height() != self.screen_h):
                self.screen_w = self.screen.get_width()
                self.screen_h = self.screen.get_height()
                self._layout()

            running     = self._handle_events()
            self._poll_controller_buttons()
            self.paused = self.options.visible

            if not self.paused:
                self._update_input(frame_dt)
                self._accumulator += frame_dt
                # Cap to 50 ms of simulated time per frame to prevent the
                # spiral-of-death when dt is very small (e.g. 1 ms).
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