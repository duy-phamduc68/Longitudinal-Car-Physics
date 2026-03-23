# -----------------------------------------------------------------------------
# ui.py - Button, CheckBox widgets and the scrollable OptionsMenu overlay
# -----------------------------------------------------------------------------

import pygame

try:
    import pyperclip
    _HAS_PYPERCLIP = True
except ImportError:
    pyperclip = None
    _HAS_PYPERCLIP = False

from constants import (
    TEXT_BRIGHT,
    TEXT_DIM,
    ACCENT,
    GRAPH_AXIS,
    BTN_NORMAL,
    BTN_HOVER,
    BTN_ACTIVE,
    GRAPH_GRID,
    GRAPH_LABELS,
    PANEL_BG,
    TIMESTEP_OPTIONS,
    FPS_OPTIONS,
    CONST_FIELDS,
    PARAM_LIMITS,
    CONST_SECTIONS,
    parse_gear_ratios,
    parse_torque_curve,
    gear_ratios_to_str,
    torque_curve_to_str,
)


def _sec_label(surface, font, text, x, y, color=None):
    col = color if color is not None else TEXT_DIM
    lbl = font.render(text, True, col)
    surface.blit(lbl, (x, y))


def _fmt_const(val):
    if isinstance(val, float):
        if abs(val - int(val)) < 1e-9:
            return str(int(val))
        return f"{val:g}"
    return str(val)


def _const_valid(txt, attr=None):
    try:
        if attr == "GEAR_RATIOS":
            parse_gear_ratios(txt)
            return True
        if attr == "TORQUE_CURVE":
            parse_torque_curve(txt)
            return True

        val = float(txt)
        if attr in PARAM_LIMITS:
            lo, hi = PARAM_LIMITS[attr]
            return lo <= val <= hi
        return True
    except (ValueError, TypeError):
        return False


class Button:
    def __init__(self, rect, label, toggle=False, active=False):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.toggle = toggle
        self.active = active
        self.disabled = False
        self._hover = False

    def handle_event(self, event, mapped_pos=None):
        if self.disabled:
            return False

        pos = mapped_pos if mapped_pos is not None else getattr(event, "pos", None)
        if pos is None:
            return False

        if event.type == pygame.MOUSEMOTION:
            self._hover = self.rect.collidepoint(pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(pos):
                if self.toggle:
                    self.active = not self.active
                return True
        return False

    def draw(self, surface, font):
        if self.disabled:
            col = (30, 32, 42)
            border_col = (55, 58, 72)
            txt_col = (80, 82, 98)
        elif self.active:
            col = BTN_ACTIVE
            border_col = ACCENT
            txt_col = TEXT_BRIGHT
        elif self._hover:
            col = BTN_HOVER
            border_col = GRAPH_AXIS
            txt_col = TEXT_BRIGHT
        else:
            col = BTN_NORMAL
            border_col = GRAPH_AXIS
            txt_col = TEXT_BRIGHT

        pygame.draw.rect(surface, col, self.rect, border_radius=5)
        pygame.draw.rect(surface, border_col, self.rect, 1, border_radius=5)
        txt = font.render(self.label, True, txt_col)
        surface.blit(txt, txt.get_rect(center=self.rect.center))


class CheckBox:
    def __init__(self, x, y, label, checked=True):
        self.rect = pygame.Rect(x, y, 18, 18)
        self.label = label
        self.checked = checked
        self._hover = False

    def handle_event(self, event, mapped_pos=None):
        pos = mapped_pos if mapped_pos is not None else getattr(event, "pos", None)
        if pos is None:
            return False

        if event.type == pygame.MOUSEMOTION:
            self._hover = self.rect.collidepoint(pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(pos):
                self.checked = not self.checked
                return True
        return False

    def draw(self, surface, font, text_color=None):
        col = BTN_HOVER if self._hover else BTN_NORMAL
        pygame.draw.rect(surface, col, self.rect, border_radius=3)
        pygame.draw.rect(surface, ACCENT, self.rect, 1, border_radius=3)
        if self.checked:
            pygame.draw.line(
                surface,
                ACCENT,
                (self.rect.x + 3, self.rect.y + 9),
                (self.rect.x + 7, self.rect.y + 14),
                2,
            )
            pygame.draw.line(
                surface,
                ACCENT,
                (self.rect.x + 7, self.rect.y + 14),
                (self.rect.x + 15, self.rect.y + 4),
                2,
            )
        if text_color is None:
            text_color = TEXT_BRIGHT
        txt = font.render(self.label, True, text_color)
        surface.blit(txt, (self.rect.right + 8, self.rect.y))


class OptionsMenu:
    _PW_MIN = 760
    _ROW = 32
    _SMALL_GAP = 8
    _SEC_GAP = 14
    _PANEL_PAD = 10
    _HEADER_H = 28

    def __init__(self, sim):
        self.sim = sim
        self.visible = False
        self.scroll_y = 0
        self.panel_x = 10
        self.panel_y = 10
        self.panel = pygame.Rect(0, 0, 0, 0)

        self._section_order = [
            "Simulation",
            "Controls",
            "Drivetrain",
            "Engine",
            "Vehicle Geometry & Mass",
            "Resistances",
        ]
        self._collapsed = {name: False for name in self._section_order}

        self._ui = {}
        self._const_texts = {}
        self._all_sections_expanded = True

        # Text editing state for options text fields
        self._cursor_pos = 0
        self._selection_anchor = None
        self._clipboard = ""
        self._mouse_dragging = False

        self._sync_const_texts()

    @property
    def editing_active(self):
        return self._ramp_editing or self._const_editing is not None

    def _sync_const_texts(self):
        car = self.sim.car
        self._const_texts = {}
        for _, attr, _, _ in CONST_FIELDS:
            if attr == "GEAR_RATIOS":
                self._const_texts[attr] = gear_ratios_to_str(car.GEAR_RATIOS)
            elif attr == "TORQUE_CURVE":
                self._const_texts[attr] = torque_curve_to_str(car.TORQUE_CURVE)
            else:
                self._const_texts[attr] = _fmt_const(getattr(car, attr))

    def _active_text(self):
        if self._ramp_editing:
            return self._ramp_text
        if self._const_editing is not None:
            return self._const_texts.get(self._const_editing, "")
        return ""

    def _set_active_text(self, text):
        if self._ramp_editing:
            self._ramp_text = text
        elif self._const_editing is not None:
            self._const_texts[self._const_editing] = text

    def _active_selection_range(self):
        if self._selection_anchor is None:
            return (self._cursor_pos, self._cursor_pos)
        return tuple(sorted((self._cursor_pos, self._selection_anchor)))

    def _has_selection(self):
        a, b = self._active_selection_range()
        return b > a

    def _clear_selection(self):
        self._selection_anchor = None

    def _ensure_cursor_bounds(self):
        txt = self._active_text()
        self._cursor_pos = max(0, min(self._cursor_pos, len(txt)))

    def _replace_selection(self, new_text):
        a, b = self._active_selection_range()
        if b <= a:
            return
        txt = self._active_text()
        txt = txt[:a] + new_text + txt[b:]
        self._set_active_text(txt)
        self._cursor_pos = a + len(new_text)
        self._clear_selection()

    def _delete_selection(self):
        if not self._has_selection():
            return False
        a, b = self._active_selection_range()
        txt = self._active_text()
        self._set_active_text(txt[:a] + txt[b:])
        self._cursor_pos = a
        self._clear_selection()
        return True

    def _select_all(self):
        txt = self._active_text()
        self._selection_anchor = 0
        self._cursor_pos = len(txt)

    def _cursor_index_from_x(self, text, rect, x, font):
        # x is in panel-local coordinates
        local = x - rect.x - 8
        if local <= 0:
            return 0
        for i in range(len(text) + 1):
            if font.size(text[:i])[0] >= local:
                return i
        return len(text)

    def _copy_selection(self):
        if not self._has_selection():
            return
        a, b = self._active_selection_range()
        text = self._active_text()[a:b]
        if _HAS_PYPERCLIP:
            try:
                pyperclip.copy(text)
            except Exception:
                self._clipboard = text
        else:
            self._clipboard = text

    def _cut_selection(self):
        self._copy_selection()
        self._delete_selection()

    def _paste_clipboard(self):
        clip = None
        if _HAS_PYPERCLIP:
            try:
                clip = pyperclip.paste()
            except Exception:
                clip = None
        if clip is None:
            clip = self._clipboard

        if not clip:
            return

        self._delete_selection()
        txt = self._active_text()
        a = self._cursor_pos
        txt = txt[:a] + clip + txt[a:]
        self._set_active_text(txt)
        self._cursor_pos = a + len(clip)

    def _commit_active_text(self):
        if self._ramp_editing:
            try:
                val = float(self._ramp_text)
                if val > 0:
                    self.sim.throttle_ramp = val
                else:
                    self._ramp_text = _fmt_const(self.sim.throttle_ramp)
            except ValueError:
                self._ramp_text = _fmt_const(self.sim.throttle_ramp)
        elif self._const_editing is not None:
            attr = self._const_editing
            current_text = self._const_texts.get(attr, "")
            if _const_valid(current_text, attr):
                self._set_constant_and_apply(attr, current_text)
            else:
                self._sync_const_texts()

    def _begin_editing(self, attr, ramp=False, cursor_pos=None):
        self._const_editing = None if ramp else attr
        self._ramp_editing = ramp
        text = self._active_text()
        if cursor_pos is None:
            self._cursor_pos = len(text)
        else:
            self._cursor_pos = max(0, min(len(text), cursor_pos))
        self._selection_anchor = self._cursor_pos

    def _handle_text_key(self, event):
        if event.type != pygame.KEYDOWN:
            return False
        if not self.editing_active:
            return False

        mods = event.mod if hasattr(event, "mod") else 0
        ctrl = bool(mods & pygame.KMOD_CTRL)
        shift = bool(mods & pygame.KMOD_SHIFT)

        key = event.key

        if ctrl and key == pygame.K_a:
            self._select_all()
            return True
        if ctrl and key == pygame.K_c:
            self._copy_selection()
            return True
        if ctrl and key == pygame.K_x:
            self._cut_selection()
            if self._const_editing and _const_valid(self._active_text(), self._const_editing):
                self._set_constant_and_apply(self._const_editing, self._active_text())
            return True
        if ctrl and key == pygame.K_v:
            self._paste_clipboard()
            if self._const_editing and _const_valid(self._active_text(), self._const_editing):
                self._set_constant_and_apply(self._const_editing, self._active_text())
            return True

        if key == pygame.K_LEFT:
            if shift and self._selection_anchor is None:
                self._selection_anchor = self._cursor_pos
            self._cursor_pos = max(0, self._cursor_pos - 1)
            if not shift:
                self._clear_selection()
            return True
        if key == pygame.K_RIGHT:
            if shift and self._selection_anchor is None:
                self._selection_anchor = self._cursor_pos
            self._cursor_pos = min(len(self._active_text()), self._cursor_pos + 1)
            if not shift:
                self._clear_selection()
            return True
        if key == pygame.K_HOME:
            if shift and self._selection_anchor is None:
                self._selection_anchor = self._cursor_pos
            self._cursor_pos = 0
            if not shift:
                self._clear_selection()
            return True
        if key == pygame.K_END:
            if shift and self._selection_anchor is None:
                self._selection_anchor = self._cursor_pos
            self._cursor_pos = len(self._active_text())
            if not shift:
                self._clear_selection()
            return True

        if key == pygame.K_BACKSPACE:
            if not self._delete_selection():
                if self._cursor_pos > 0:
                    txt = self._active_text()
                    self._set_active_text(txt[: self._cursor_pos - 1] + txt[self._cursor_pos :])
                    self._cursor_pos -= 1
            self._clear_selection()
            if self._const_editing and _const_valid(self._active_text(), self._const_editing):
                self._set_constant_and_apply(self._const_editing, self._active_text())
            return True

        if key == pygame.K_DELETE:
            if not self._delete_selection():
                txt = self._active_text()
                if self._cursor_pos < len(txt):
                    self._set_active_text(txt[: self._cursor_pos] + txt[self._cursor_pos + 1 :])
            self._clear_selection()
            if self._const_editing and _const_valid(self._active_text(), self._const_editing):
                self._set_constant_and_apply(self._const_editing, self._active_text())
            return True

        if key in (pygame.K_RETURN, pygame.K_TAB):
            self._commit_active_text()
            if key == pygame.K_TAB and self._const_editing is not None:
                attrs = self._all_const_attrs()
                idx = attrs.index(self._const_editing) if self._const_editing in attrs else -1
                if idx >= 0:
                    next_idx = (idx + 1) % len(attrs)
                    self._begin_editing(attrs[next_idx], ramp=False)
            else:
                self._const_editing = None
                self._ramp_editing = False
            return True

        if key == pygame.K_ESCAPE:
            self._const_editing = None
            self._ramp_editing = False
            self._sync_const_texts()
            self._ramp_text = _fmt_const(self.sim.throttle_ramp)
            self._clear_selection()
            return True

        if event.unicode and len(event.unicode) == 1 and event.unicode.isprintable() and not ctrl:
            txt = self._active_text()
            if self._has_selection():
                self._delete_selection()
                txt = self._active_text()
            # limit constant and ramp text length similarly to previous behavior
            limit = 24 if self._ramp_editing else 240
            if len(txt) < limit:
                self._set_active_text(txt[: self._cursor_pos] + event.unicode + txt[self._cursor_pos :])
                self._cursor_pos += 1
                if self._const_editing and _const_valid(self._active_text(), self._const_editing):
                    self._set_constant_and_apply(self._const_editing, self._active_text())
            return True

        return False

    def _clamp_value(self, attr, val):
        if attr in PARAM_LIMITS:
            lo, hi = PARAM_LIMITS[attr]
            return max(lo, min(hi, val))
        return val

    def _get_default_value(self, attr):
        for _, a, _, default in CONST_FIELDS:
            if a == attr:
                return default
        return None

    def _limit_placeholder(self, attr):
        default_val = self._get_default_value(attr)
        if attr in PARAM_LIMITS:
            lo, hi = PARAM_LIMITS[attr]
            if default_val is not None:
                return f"default: {_fmt_const(default_val)}; {lo:g} - {hi:g}"
            return f"{lo:g} - {hi:g}"

        if default_val is not None:
            # for constants with default but no explicit limits
            return _fmt_const(default_val)
        return ""

    def _ramp_placeholder(self):
        return f"default: {_fmt_const(self.sim.throttle_ramp)}; 0.1 - 10.0"
    def _set_constant_and_apply(self, attr, raw_val):
        car = self.sim.car
        if not hasattr(car, attr):
            return False

        changed = False
        try:
            if attr == "GEAR_RATIOS":
                parsed = parse_gear_ratios(raw_val)
                if parsed != car.GEAR_RATIOS:
                    car.GEAR_RATIOS = parsed
                    changed = True
            elif attr == "TORQUE_CURVE":
                parsed = parse_torque_curve(raw_val)
                if parsed != car.TORQUE_CURVE:
                    car.TORQUE_CURVE = parsed
                    changed = True
            elif attr in ("b", "c", "L"):
                val = self._clamp_value(attr, float(raw_val))
                b_val = car.b
                c_val = car.c
                l_val = car.L

                if attr == "b":
                    b_val = self._clamp_value("b", val)
                    l_val = self._clamp_value("L", b_val + c_val)
                    c_val = self._clamp_value("c", l_val - b_val)
                    b_val = l_val - c_val
                elif attr == "c":
                    c_val = self._clamp_value("c", val)
                    l_val = self._clamp_value("L", b_val + c_val)
                    b_val = self._clamp_value("b", l_val - c_val)
                    c_val = l_val - b_val
                else:
                    l_val = self._clamp_value("L", val)
                    b_val = self._clamp_value("b", b_val)
                    c_val = self._clamp_value("c", l_val - b_val)
                    b_val = l_val - c_val

                if abs(car.b - b_val) > 1e-9:
                    car.b = b_val
                    changed = True
                if abs(car.c - c_val) > 1e-9:
                    car.c = c_val
                    changed = True
                if abs(car.L - l_val) > 1e-9:
                    car.L = l_val
                    changed = True
            else:
                val = self._clamp_value(attr, float(raw_val))
                if attr == "RPM_REDLINE":
                    val = max(val, car.RPM_IDLE + 250.0)
                if attr == "RPM_IDLE":
                    val = min(val, car.RPM_REDLINE - 250.0)

                cur = getattr(car, attr)
                if abs(cur - val) > 1e-9:
                    setattr(car, attr, val)
                    changed = True
        except (ValueError, TypeError):
            return False

        if changed:
            self._sync_const_texts()
            self.sim.reset_scenario()
        return changed

    def _all_const_attrs(self):
        attrs = []
        for _, fields in CONST_SECTIONS:
            for _, attr, _, _ in fields:
                attrs.append(attr)
        return attrs

    def _panel_width(self):
        return max(self._PW_MIN, int(self.sim.screen_w * 0.8))

    def _rebuild_layout(self, viewport_h, pw):
        row = self._ROW
        gap = self._SMALL_GAP
        sec_gap = self._SEC_GAP
        pad = self._PANEL_PAD
        header_h = self._HEADER_H

        x0 = 0
        y = 12

        self._ui = {
            "section_headers": {},
            "section_bodies": {},
            "const_rects": {},
            "ts_buttons": [],
            "fps_buttons": [],
            "comb_checks": [],
            "graph_buttons": {},
            "expand_btn": None,
            "close_btn": None,
            "reset_btn": None,
            "ramp_rect": None,
            "auto_shift_rect": None,
            "model2_visual_rect": None,
        }

        title_h = 28
        expand_label = "Collapse All" if self._all_sections_expanded else "Expand All"
        self._ui["expand_btn"] = Button(pygame.Rect(pw - 150, 7, 130, 24), expand_label)
        y += title_h

        # Simulation section
        header_rect = pygame.Rect(x0 + 10, y, pw - 20, header_h)
        self._ui["section_headers"]["Simulation"] = header_rect
        y += header_h
        if not self._collapsed["Simulation"]:
            body_top = y
            inner_x = x0 + 22
            inner_w = pw - 44

            # Timestep
            y += 2
            ts_y = y + 18
            for i, (dt, label) in enumerate(TIMESTEP_OPTIONS):
                r = pygame.Rect(inner_x, ts_y + i * (row + gap), inner_w, row)
                btn = Button(r, label, toggle=True, active=(dt == self.sim.dt))
                self._ui["ts_buttons"].append((dt, btn))
            y = ts_y + len(TIMESTEP_OPTIONS) * (row + gap) + sec_gap

            # FPS
            fps_label_y = y
            fps_y = y + 18
            col_w = max(1, inner_w // len(FPS_OPTIONS))
            for i, fps in enumerate(FPS_OPTIONS):
                r = pygame.Rect(inner_x + i * col_w, fps_y, col_w - 6, row)
                btn = Button(r, str(fps), toggle=True, active=(fps == self.sim.target_fps))
                self._ui["fps_buttons"].append((fps, btn))
            y = fps_y + row + sec_gap

            # Graph mode
            graph_label_y = y
            g_y = y + 18
            b1 = Button(
                pygame.Rect(inner_x, g_y, 150, row),
                "Full Mode",
                toggle=True,
                active=(self.sim.graph_mode == "full"),
            )
            b2 = Button(
                pygame.Rect(inner_x + 160, g_y, 170, row),
                "Combined Mode",
                toggle=True,
                active=(self.sim.graph_mode == "combined"),
            )
            self._ui["graph_buttons"] = {
                "full": b1,
                "combined": b2,
            }
            y = g_y + row + 6

            # Combined channels
            cc_label_y = y
            cc_y = y + 18
            self._ui["comb_checks"] = []
            for i, lbl in enumerate(GRAPH_LABELS):
                cx = inner_x + (i % 2) * ((inner_w // 2) + 8)
                cy = cc_y + (i // 2) * 24
                cb = CheckBox(cx, cy, lbl, checked=self.sim.combined_channels[i])
                self._ui["comb_checks"].append(cb)
            y = cc_y + ((len(GRAPH_LABELS) + 1) // 2) * 24 + 10

            self._ui["section_bodies"]["Simulation"] = {
                "rect": pygame.Rect(x0 + 10, body_top, pw - 20, y - body_top),
                "labels": {
                    "timestep": (inner_x, ts_y - 16),
                    "fps": (inner_x, fps_label_y + 2),
                    "graph": (inner_x, graph_label_y + 2),
                    "combined": (inner_x, cc_label_y + 2),
                },
            }

        y += sec_gap

        header_rect = pygame.Rect(x0 + 10, y, pw - 20, header_h)
        self._ui["section_headers"]["Controls"] = header_rect
        y += header_h

        if not self._collapsed["Controls"]:
            body_top = y
            inner_x = x0 + 22
            inner_w = pw - 44

            ramp_label_y = y + 6
            ramp_rect = pygame.Rect(inner_x + 240, ramp_label_y, inner_w - 250, row)
            self._ui["ramp_rect"] = ramp_rect

            auto_y = ramp_label_y + row + 14
            auto_rect = pygame.Rect(inner_x, auto_y, 22, 22)
            self._ui["auto_shift_rect"] = auto_rect

            model2_y = auto_y + 30
            model2_rect = pygame.Rect(inner_x, model2_y, 22, 22)
            self._ui["model2_visual_rect"] = model2_rect

            y = model2_y + 30
            self._ui["section_bodies"]["Controls"] = {
                "rect": pygame.Rect(x0 + 10, body_top, pw - 20, y - body_top),
                "labels": {
                    "ramp": (inner_x, ramp_label_y + 8),
                    "auto": (inner_x + 30, auto_y + 2),
                    "model2": (inner_x + 30, model2_y + 2),
                },
            }

        y += sec_gap

        # Drivetrain + Engine + Vehicle + Resistances + Tires
        sec_map = {name: fields for name, fields in CONST_SECTIONS}
        for sec_name in [
            "Drivetrain",
            "Engine",
            "Vehicle Geometry & Mass",
            "Resistances",
        ]:
            header_rect = pygame.Rect(x0 + 10, y, pw - 20, header_h)
            self._ui["section_headers"][sec_name] = header_rect
            y += header_h

            if not self._collapsed[sec_name]:
                body_top = y
                inner_x = x0 + 22
                inner_w = pw - 44
                label_w = 320
                input_x = inner_x + label_w
                input_w = inner_w - label_w - 12

                local_y = y + 6
                if sec_name == "Drivetrain":
                    local_y += 18

                for display_name, attr, unit, _default in sec_map[sec_name]:
                    rr = pygame.Rect(input_x, local_y, input_w, row)
                    self._ui["const_rects"][attr] = {
                        "rect": rr,
                        "label": display_name,
                        "unit": unit,
                        "label_pos": (inner_x, local_y + 8),
                    }
                    local_y += row + gap

                if sec_name == "Drivetrain":
                    self._ui["drivetrain_gear_pos"] = (inner_x, y + 6)

                y = local_y + 8
                self._ui["section_bodies"][sec_name] = {
                    "rect": pygame.Rect(x0 + 10, body_top, pw - 20, y - body_top)
                }

            y += sec_gap

        help_y = y
        self._ui["help_y"] = help_y
        y += 68

        reset_w = 210
        close_w = 130
        btn_y = y
        self._ui["reset_btn"] = Button(pygame.Rect((pw // 2) - reset_w - 8, btn_y + 10, reset_w, row + 2), "Reset Scenario")
        self._ui["close_btn"] = Button(pygame.Rect((pw // 2) + 8, btn_y + 10, close_w, row + 2), "Close")
        y = btn_y + row + 18

        self._total_height = y + 10

    def _map_mouse(self, event):
        pos = getattr(event, "pos", None)
        if pos and self.panel.collidepoint(pos):
            return (pos[0] - self.panel.x, pos[1] - self.panel.y + self.scroll_y)
        return None

    def toggle(self):
        self.visible = not self.visible
        if self.visible:
            self.scroll_y = 0
            self._sync_const_texts()
            self._ramp_text = _fmt_const(self.sim.throttle_ramp)
            self._const_editing = None
            self._ramp_editing = False

    def handle_event(self, event):
        if not self.visible:
            return False

        pw = self._panel_width()
        viewport_h = min(self._total_height if hasattr(self, "_total_height") else 900, self.sim.screen_h - 40)
        panel_x = max(10, (self.sim.screen_w - pw) // 2)
        self.panel = pygame.Rect(panel_x, self.panel_y, pw, viewport_h)
        self._rebuild_layout(viewport_h, pw)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = getattr(event, "pos", None)
            if pos and not self.panel.collidepoint(pos):
                self.visible = False
                self._const_editing = None
                self._ramp_editing = False
                return True

        # Mouse-wheel scrolling
        if event.type == pygame.MOUSEWHEEL:
            if self.panel.collidepoint(pygame.mouse.get_pos()):
                self.scroll_y -= event.y * 32
                max_scroll = max(0, self._total_height - viewport_h)
                self.scroll_y = max(0, min(self.scroll_y, max_scroll))
                return True

        mapped_pos = self._map_mouse(event)

        # Toggle expand/collapse all button
        if self._ui.get("expand_btn") and self._ui["expand_btn"].handle_event(event, mapped_pos):
            self._all_sections_expanded = not self._all_sections_expanded
            for sec_name in self._collapsed:
                self._collapsed[sec_name] = not self._all_sections_expanded
            return True

        # Toggle collapsed sections
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and mapped_pos:
            for sec_name, rect in self._ui["section_headers"].items():
                if rect.collidepoint(mapped_pos):
                    self._collapsed[sec_name] = not self._collapsed[sec_name]
                    self._const_editing = None
                    self._ramp_editing = False
                    return True

        # Reset and close buttons
        if self._ui["reset_btn"] and self._ui["reset_btn"].handle_event(event, mapped_pos):
            self.sim.reset_scenario()
            self._sync_const_texts()
            self._ramp_text = _fmt_const(self.sim.throttle_ramp)
            return True

        if self._ui["close_btn"] and self._ui["close_btn"].handle_event(event, mapped_pos):
            self.visible = False
            return True

        # Simulation section controls
        for dt, btn in self._ui["ts_buttons"]:
            if btn.handle_event(event, mapped_pos):
                for dt2, b2 in self._ui["ts_buttons"]:
                    b2.active = (dt2 == dt)
                if dt != self.sim.dt:
                    self.sim.dt = dt
                    self.sim.reset_scenario()
                return True

        for fps, btn in self._ui["fps_buttons"]:
            if btn.handle_event(event, mapped_pos):
                for fps2, b2 in self._ui["fps_buttons"]:
                    b2.active = (fps2 == fps)
                self.sim.target_fps = fps
                return True

        gbtns = self._ui["graph_buttons"]
        if gbtns:
            if gbtns["full"].handle_event(event, mapped_pos):
                self.sim.graph_mode = "full"
                gbtns["full"].active = True
                gbtns["combined"].active = False
                return True
            if gbtns["combined"].handle_event(event, mapped_pos):
                self.sim.graph_mode = "combined"
                gbtns["full"].active = False
                gbtns["combined"].active = True
                return True

        for i, cb in enumerate(self._ui["comb_checks"]):
            if cb.handle_event(event, mapped_pos):
                self.sim.combined_channels[i] = cb.checked
                return True

        # Controls section
        ramp_rect = self._ui.get("ramp_rect")
        auto_rect = self._ui.get("auto_shift_rect")
        model2_rect = self._ui.get("model2_visual_rect")

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._mouse_dragging = True
            if auto_rect and mapped_pos and auto_rect.collidepoint(mapped_pos):
                self.sim.enable_auto_shift = not self.sim.enable_auto_shift
                return True

            if model2_rect and mapped_pos and model2_rect.collidepoint(mapped_pos):
                self.sim.show_model2_elements = not self.sim.show_model2_elements
                return True

            if ramp_rect and mapped_pos and ramp_rect.collidepoint(mapped_pos):
                cursor = self._cursor_index_from_x(self._ramp_text, ramp_rect, mapped_pos[0], self.sim.font_sm)
                self._begin_editing(None, ramp=True, cursor_pos=cursor)
                return True

            if mapped_pos:
                for attr, info in self._ui["const_rects"].items():
                    if info["rect"].collidepoint(mapped_pos):
                        cursor = self._cursor_index_from_x(self._const_texts.get(attr, ""), info["rect"], mapped_pos[0], self.sim.font_sm)
                        self._begin_editing(attr, ramp=False, cursor_pos=cursor)
                        break
            else:
                self._const_editing = None
                self._ramp_editing = False
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._mouse_dragging = False

        if event.type == pygame.MOUSEMOTION and self._mouse_dragging and mapped_pos and self.editing_active:
            if self._ramp_editing and ramp_rect and ramp_rect.collidepoint(mapped_pos):
                cursor = self._cursor_index_from_x(self._ramp_text, ramp_rect, mapped_pos[0], self.sim.font_sm)
                self._cursor_pos = cursor
                return True
            if self._const_editing is not None:
                info = self._ui["const_rects"].get(self._const_editing)
                if info and info["rect"].collidepoint(mapped_pos):
                    cursor = self._cursor_index_from_x(self._active_text(), info["rect"], mapped_pos[0], self.sim.font_sm)
                    self._cursor_pos = cursor
                    return True

        if self._handle_text_key(event):
            return True

        return True

    def draw(self, surface, font_sm, font_md):
        if not self.visible:
            return

        pw = self._panel_width()
        viewport_h = min(self._total_height if hasattr(self, "_total_height") else 900, surface.get_height() - 40)
        panel_x = max(10, (surface.get_width() - pw) // 2)
        self.panel = pygame.Rect(panel_x, self.panel_y, pw, viewport_h)
        self._rebuild_layout(viewport_h, pw)

        max_scroll = max(0, self._total_height - viewport_h)
        self.scroll_y = max(0, min(self.scroll_y, max_scroll))

        overlay = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        surface.blit(overlay, (0, 0))

        panel_bg = pygame.Surface((pw, viewport_h), pygame.SRCALPHA)
        pygame.draw.rect(panel_bg, PANEL_BG, panel_bg.get_rect(), border_radius=6)
        pygame.draw.rect(panel_bg, ACCENT, panel_bg.get_rect(), 1, border_radius=6)
        surface.blit(panel_bg, self.panel.topleft)

        content = pygame.Surface((pw, self._total_height), pygame.SRCALPHA)

        title = font_md.render("Options - Model 4", True, TEXT_BRIGHT)
        content.blit(title, (16, 12))

        expand_btn = self._ui.get("expand_btn")
        if expand_btn:
            expand_btn.label = "Collapse All" if self._all_sections_expanded else "Expand All"
            expand_btn.draw(content, font_sm)

        # Section headers and body panels
        for sec_name in self._section_order:
            hdr = self._ui["section_headers"].get(sec_name)
            if hdr is None:
                continue

            pygame.draw.rect(content, (34, 38, 50), hdr, border_radius=6)
            pygame.draw.rect(content, GRAPH_AXIS, hdr, 1, border_radius=6)
            marker = "+" if self._collapsed[sec_name] else "-"
            htxt = font_sm.render(f"{marker} {sec_name}", True, TEXT_BRIGHT)
            content.blit(htxt, (hdr.x + 10, hdr.y + 6))

            body = self._ui["section_bodies"].get(sec_name)
            if body:
                pygame.draw.rect(content, (23, 26, 35), body["rect"], border_radius=6)
                pygame.draw.rect(content, (56, 61, 78), body["rect"], 1, border_radius=6)

        # Simulation section drawing
        sim_body = self._ui["section_bodies"].get("Simulation")
        if sim_body:
            labels = sim_body["labels"]
            _sec_label(content, font_sm, "Timestep", *labels["timestep"])
            for _, btn in self._ui["ts_buttons"]:
                btn.draw(content, font_sm)

            _sec_label(content, font_sm, "Target FPS", *labels["fps"])
            for _, btn in self._ui["fps_buttons"]:
                btn.draw(content, font_sm)

            _sec_label(content, font_sm, "Graph Mode", *labels["graph"])
            self._ui["graph_buttons"]["full"].draw(content, font_sm)
            self._ui["graph_buttons"]["combined"].draw(content, font_sm)

            _sec_label(content, font_sm, "Combined Channels", *labels["combined"])
            for cb in self._ui["comb_checks"]:
                cb.draw(content, font_sm)

        # Drivetrain current gear status
        gear_pos = self._ui.get("drivetrain_gear_pos")
        if gear_pos:
            gear_text = font_sm.render(f"Current Gear: {self.sim.car.gear}", True, ACCENT)
            content.blit(gear_text, gear_pos)

        # Constant fields drawing
        for attr, info in self._ui["const_rects"].items():
            rect = info["rect"]
            label = info["label"]
            unit = info["unit"]
            label_pos = info["label_pos"]

            txt_str = self._const_texts.get(attr, "")
            is_active = (self._const_editing == attr)
            valid = _const_valid(txt_str, attr)

            content.blit(font_sm.render(f"{label}", True, TEXT_DIM), label_pos)
            unit_lbl = font_sm.render(f"[{unit}]", True, (120, 125, 145))
            content.blit(unit_lbl, (label_pos[0] + 180, label_pos[1]))

            if is_active:
                box_col = (30, 40, 60)
                border_col = ACCENT
            elif not valid:
                box_col = (58, 23, 23)
                border_col = (200, 70, 70)
            else:
                box_col = BTN_NORMAL
                border_col = GRAPH_AXIS

            pygame.draw.rect(content, box_col, rect, border_radius=4)
            pygame.draw.rect(content, border_col, rect, 1, border_radius=4)

            # Draw selection highlight
            text_content = txt_str
            if is_active and not text_content:
                placeholder = self._limit_placeholder(attr)
                text_content = placeholder
                display_color = TEXT_DIM
            else:
                display_color = TEXT_BRIGHT

            if is_active and self._has_selection() and txt_str:
                a, b = self._active_selection_range()
                before = txt_str[:a]
                selected = txt_str[a:b]
                selection_x = rect.x + 8 + font_sm.size(before)[0]
                selection_w = max(1, font_sm.size(selected)[0])
                pygame.draw.rect(
                    content,
                    (60, 90, 160),
                    (selection_x, rect.y + 6, selection_w, rect.height - 12),
                )

            content.blit(font_sm.render(text_content, True, display_color), (rect.x + 8, rect.y + 8))

            # Draw caret
            if is_active:
                caret_x = rect.x + 8 + font_sm.size((txt_str or "")[: self._cursor_pos])[0]
                pygame.draw.line(content, TEXT_BRIGHT, (caret_x, rect.y + 6), (caret_x, rect.y + rect.height - 6), 1)

        # Controls section drawing
        controls_body = self._ui["section_bodies"].get("Controls")
        if controls_body:
            labels = controls_body["labels"]
            ramp_rect = self._ui["ramp_rect"]
            auto_rect = self._ui["auto_shift_rect"]
            model2_rect = self._ui["model2_visual_rect"]

            content.blit(font_sm.render("Throttle Ramp", True, TEXT_DIM), labels["ramp"])
            content.blit(font_sm.render("[s]", True, (120, 125, 145)), (labels["ramp"][0] + 120, labels["ramp"][1]))
            pygame.draw.rect(content, BTN_NORMAL, ramp_rect, border_radius=4)
            pygame.draw.rect(content, ACCENT if self._ramp_editing else GRAPH_AXIS, ramp_rect, 1, border_radius=4)

            # Ramp text selection + caret
            ramp_content = self._ramp_text
            ramp_color = TEXT_BRIGHT
            if self._ramp_editing and not ramp_content:
                ramp_content = self._ramp_placeholder()
                ramp_color = TEXT_DIM

            if self._ramp_editing and self._has_selection() and self._ramp_text:
                a, b = self._active_selection_range()
                before = self._ramp_text[:a]
                selected = self._ramp_text[a:b]
                selection_x = ramp_rect.x + 8 + font_sm.size(before)[0]
                selection_w = max(1, font_sm.size(selected)[0])
                pygame.draw.rect(
                    content,
                    (60, 90, 160),
                    (selection_x, ramp_rect.y + 6, selection_w, ramp_rect.height - 12),
                )

            content.blit(font_sm.render(ramp_content, True, ramp_color), (ramp_rect.x + 8, ramp_rect.y + 8))
            if self._ramp_editing:
                caret_x = ramp_rect.x + 8 + font_sm.size((self._ramp_text or "")[: self._cursor_pos])[0]
                pygame.draw.line(content, TEXT_BRIGHT, (caret_x, ramp_rect.y + 6), (caret_x, ramp_rect.y + ramp_rect.height - 6), 1)

            pygame.draw.rect(content, BTN_NORMAL, auto_rect, border_radius=3)
            pygame.draw.rect(content, ACCENT, auto_rect, 1, border_radius=3)
            if self.sim.enable_auto_shift:
                pygame.draw.line(content, ACCENT, (auto_rect.x + 4, auto_rect.y + 11), (auto_rect.x + 8, auto_rect.y + 16), 2)
                pygame.draw.line(content, ACCENT, (auto_rect.x + 8, auto_rect.y + 16), (auto_rect.x + 18, auto_rect.y + 6), 2)
            content.blit(font_sm.render("Enable Auto Shift", True, TEXT_BRIGHT), labels["auto"])

            pygame.draw.rect(content, BTN_NORMAL, model2_rect, border_radius=3)
            pygame.draw.rect(content, ACCENT, model2_rect, 1, border_radius=3)
            if self.sim.show_model2_elements:
                pygame.draw.line(content, ACCENT, (model2_rect.x + 4, model2_rect.y + 11), (model2_rect.x + 8, model2_rect.y + 16), 2)
                pygame.draw.line(content, ACCENT, (model2_rect.x + 8, model2_rect.y + 16), (model2_rect.x + 18, model2_rect.y + 6), 2)
            content.blit(font_sm.render("Show Load-Transfer Visual Elements", True, TEXT_BRIGHT), labels["model2"])

        # Action buttons
        self._ui["reset_btn"].draw(content, font_md)
        self._ui["close_btn"].draw(content, font_sm)

        # Help text
        help_y = self._ui["help_y"]
        _sec_label(content, font_sm, "Input guide", 22, help_y)
        help_lines = [
            "Keyboard: W throttle, Space brake, D shift up, A shift down",
            "Controller: RT throttle, LT brake, B shift up, X shift down",
            "Malformed drivetrain inputs are rejected and previous values are kept",
        ]
        for i, line in enumerate(help_lines):
            content.blit(font_sm.render(line, True, TEXT_DIM), (22, help_y + 18 + i * 18))

        surface.blit(content, self.panel.topleft, area=pygame.Rect(0, self.scroll_y, pw, viewport_h))

        # Scroll bar
        if max_scroll > 0:
            bar_w = 6
            bar_h = max(20, int(viewport_h * (viewport_h / self._total_height)))
            bar_x = self.panel.right - 10
            bar_y = self.panel.y + int((self.scroll_y / max_scroll) * (viewport_h - bar_h))
            pygame.draw.rect(surface, GRAPH_AXIS, (bar_x, bar_y, bar_w, bar_h), border_radius=3)
