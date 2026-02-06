import logging
import os
import pathlib

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, Gtk

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Controls")
        super().__init__(screen, title)

        self.content.get_style_context().add_class("workcell-bg")
        self.compact_mode = not self._screen.vertical_mode and self._screen.width <= 800 and self._screen.height <= 480
        self.distance = "10"
        self.temp_step = 5
        self.motion_locked = False
        self.motion_buttons = []

        styles_dir = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles")
        self.paths = {
            "mark": os.path.join(styles_dir, "workcell-mark.svg"),
            "home": os.path.join(styles_dir, "home.svg"),
            "home_active": os.path.join(styles_dir, "home-dark.svg"),
            "settings": os.path.join(styles_dir, "sliders.svg"),
            "settings_active": os.path.join(styles_dir, "sliders-dark.svg"),
            "files": os.path.join(styles_dir, "menu-bars.svg"),
            "files_active": os.path.join(styles_dir, "menu-bars-dark.svg"),
            "spool": os.path.join(styles_dir, "spool-nav.svg"),
            "spool_active": os.path.join(styles_dir, "spool-nav-dark.svg"),
            "temp_nozzle": os.path.join(styles_dir, "thermometer-nozzle.svg"),
            "temp_bed": os.path.join(styles_dir, "thermometer-bed.svg"),
        }

        self.current_extruder = self._printer.get_stat("toolhead", "extruder") or "extruder"
        self.temp_labels = {}
        self.distance_buttons = {}

        root_orientation = Gtk.Orientation.VERTICAL if self._screen.vertical_mode else Gtk.Orientation.HORIZONTAL
        self.root = Gtk.Box(orientation=root_orientation, spacing=0)
        self.root.get_style_context().add_class("workcell-root")
        if self.compact_mode:
            self.root.get_style_context().add_class("workcell-compact")
        self.content.add(self.root)

        self.sidebar = self.create_sidebar()
        self.root.pack_start(self.sidebar, False, False, 0)

        self.main_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10 if self.compact_mode else 18)
        self.main_area.get_style_context().add_class("workcell-main-area")
        if self._screen.vertical_mode:
            self.main_area.set_margin_top(14)
            self.main_area.set_margin_start(14)
            self.main_area.set_margin_end(14)
            self.main_area.set_margin_bottom(14)
        elif self.compact_mode:
            self.main_area.set_margin_top(8)
            self.main_area.set_margin_start(8)
            self.main_area.set_margin_end(8)
            self.main_area.set_margin_bottom(8)
        else:
            self.main_area.set_margin_top(18)
            self.main_area.set_margin_start(20)
            self.main_area.set_margin_end(20)
            self.main_area.set_margin_bottom(18)
        self.root.pack_start(self.main_area, True, True, 0)

        self.main_area.pack_start(self.build_distance_row(), False, False, 0)
        self.main_area.pack_start(self.build_motion_row(), True, True, 0)
        self.main_area.pack_end(self.build_temp_row(), False, False, 0)

        self.update_temp_controls()
        self.update_motion_lock()

    def _image_from_file(self, path, width, height):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, width, height)
            return Gtk.Image.new_from_pixbuf(pixbuf)
        except Exception as err:
            logging.debug(f"Unable to load image {path}: {err}")
            return Gtk.Image()

    def create_sidebar(self):
        orientation = Gtk.Orientation.HORIZONTAL if self._screen.vertical_mode else Gtk.Orientation.VERTICAL
        sidebar = Gtk.Box(orientation=orientation, spacing=8 if self.compact_mode else 12)
        sidebar.get_style_context().add_class("workcell-sidebar")

        if self._screen.vertical_mode:
            sidebar.set_margin_top(8)
            sidebar.set_margin_start(8)
            sidebar.set_margin_end(8)
            sidebar.set_margin_bottom(8)
        else:
            sidebar_width = 92 if self.compact_mode else max(int(self._screen.width * 0.13), 130)
            sidebar.set_size_request(sidebar_width, -1)
            if self.compact_mode:
                sidebar.set_margin_top(6)
                sidebar.set_margin_start(6)
                sidebar.set_margin_end(6)
                sidebar.set_margin_bottom(6)
            else:
                sidebar.set_margin_top(10)
                sidebar.set_margin_start(10)
                sidebar.set_margin_end(10)
                sidebar.set_margin_bottom(10)

        mark_size = 52 if self._screen.vertical_mode else (42 if self.compact_mode else 66)
        sidebar.pack_start(self._image_from_file(self.paths["mark"], mark_size, mark_size), False, False, 0)

        if self._screen.vertical_mode:
            button_size, icon_size = 76, 36
        elif self.compact_mode:
            button_size, icon_size = 64, 30
        else:
            button_size, icon_size = 96, 46

        sidebar.pack_start(
            self._nav_button(self.paths["home"], button_size, icon_size, self.go_home), False, False, 0
        )
        sidebar.pack_start(
            self._nav_button(self.paths["settings_active"], button_size, icon_size, self.go_controls, is_active=True),
            False,
            False,
            0,
        )
        sidebar.pack_start(
            self._nav_button(self.paths["files"], button_size, icon_size, self.go_queue), False, False, 0
        )
        sidebar.pack_start(
            self._nav_button(self.paths["spool"], button_size, icon_size, self.go_filament), False, False, 0
        )
        return sidebar

    def _nav_button(self, icon_path, button_size, icon_size, callback, is_active=False):
        button = Gtk.Button()
        button.get_style_context().add_class("workcell-nav-button")
        if is_active:
            button.get_style_context().add_class("workcell-nav-button-active")
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.set_size_request(button_size, button_size)
        button.add(self._image_from_file(icon_path, icon_size, icon_size))
        button.connect("clicked", callback)
        return button

    def build_distance_row(self):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10 if self.compact_mode else 14)
        row.get_style_context().add_class("workcell-distance-row")

        for dist in ("1", "10", "50"):
            button = Gtk.Button(label=f"{dist}mm")
            button.get_style_context().add_class("workcell-distance-button")
            button.connect("clicked", self.set_distance, dist)
            button.set_hexpand(True)
            self.distance_buttons[dist] = button
            row.pack_start(button, True, True, 0)

        self._refresh_distance_buttons()
        return row

    def build_motion_row(self):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18 if self.compact_mode else 28)

        xy_block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8 if self.compact_mode else 12)
        xy_label = Gtk.Label(label="X/Y")
        xy_label.get_style_context().add_class("workcell-axis-label")
        xy_label.set_halign(Gtk.Align.START)
        xy_block.pack_start(xy_label, False, False, 0)

        xy_grid = Gtk.Grid(row_spacing=8 if self.compact_mode else 10, column_spacing=8 if self.compact_mode else 10)
        xy_grid.set_halign(Gtk.Align.START)
        xy_grid.set_valign(Gtk.Align.CENTER)

        up = self._jog_button("^", self.move_axis, "Y", "+")
        down = self._jog_button("v", self.move_axis, "Y", "-")
        left = self._jog_button("<", self.move_axis, "X", "-")
        right = self._jog_button(">", self.move_axis, "X", "+")

        home = Gtk.Button()
        home.get_style_context().add_class("workcell-jog-button")
        home.get_style_context().add_class("workcell-jog-home")
        icon_size = 30 if self.compact_mode else 40
        home.add(self._image_from_file(self.paths["home"], icon_size, icon_size))
        home.connect("clicked", self.home_axes)
        self.motion_buttons.append(home)

        xy_grid.attach(up, 1, 0, 1, 1)
        xy_grid.attach(left, 0, 1, 1, 1)
        xy_grid.attach(home, 1, 1, 1, 1)
        xy_grid.attach(right, 2, 1, 1, 1)
        xy_grid.attach(down, 1, 2, 1, 1)
        xy_block.pack_start(xy_grid, True, True, 0)

        z_block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8 if self.compact_mode else 12)
        z_label = Gtk.Label(label="Z")
        z_label.get_style_context().add_class("workcell-axis-label")
        z_label.set_halign(Gtk.Align.START)
        z_block.pack_start(z_label, False, False, 0)

        z_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8 if self.compact_mode else 10)
        z_up = self._jog_button("^", self.move_axis, "Z", "+")
        z_down = self._jog_button("v", self.move_axis, "Z", "-")
        z_row.pack_start(z_up, True, True, 0)
        z_row.pack_start(z_down, True, True, 0)
        z_block.pack_start(z_row, False, False, 0)

        row.pack_start(xy_block, True, True, 0)
        row.pack_start(z_block, True, True, 0)
        return row

    def _jog_button(self, label, callback, axis, direction):
        button = Gtk.Button(label=label)
        button.get_style_context().add_class("workcell-jog-button")
        button.connect("clicked", callback, axis, direction)
        self.motion_buttons.append(button)
        return button

    def build_temp_row(self):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12 if self.compact_mode else 20)
        row.set_hexpand(True)

        row.pack_start(
            self._build_temp_control(
                key="nozzle",
                label=_("Nozzle"),
                icon_path=self.paths["temp_nozzle"],
                icon_class="workcell-temp-icon-nozzle",
                device_getter=lambda: self.current_extruder,
            ),
            True,
            True,
            0,
        )
        row.pack_start(
            self._build_temp_control(
                key="bed",
                label=_("Bed"),
                icon_path=self.paths["temp_bed"],
                icon_class="workcell-temp-icon-bed",
                device_getter=lambda: "heater_bed",
            ),
            True,
            True,
            0,
        )
        return row

    def _build_temp_control(self, key, label, icon_path, icon_class, device_getter):
        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8 if self.compact_mode else 12)
        card.get_style_context().add_class("workcell-temp-adjust-card")
        card.set_hexpand(True)

        minus = Gtk.Button(label="-")
        minus.get_style_context().add_class("workcell-square-button")
        minus.connect("clicked", self.adjust_temp, key, -self.temp_step, device_getter)

        plus = Gtk.Button(label="+")
        plus.get_style_context().add_class("workcell-square-button")
        plus.connect("clicked", self.adjust_temp, key, self.temp_step, device_getter)

        center = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8 if self.compact_mode else 10)
        center.set_hexpand(True)
        icon_size = 28 if self.compact_mode else 36
        icon = self._image_from_file(icon_path, icon_size, icon_size)
        icon.get_style_context().add_class(icon_class)
        center.pack_start(icon, False, False, 0)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        text_box.set_hexpand(True)
        title_label = Gtk.Label(label=label, xalign=0)
        title_label.get_style_context().add_class("workcell-temp-title")
        value_label = Gtk.Label(label="--°", xalign=0)
        value_label.get_style_context().add_class("workcell-temp-value")
        text_box.pack_start(title_label, False, False, 0)
        text_box.pack_start(value_label, False, False, 0)
        center.pack_start(text_box, True, True, 0)

        card.pack_start(minus, False, False, 0)
        card.pack_start(center, True, True, 0)
        card.pack_start(plus, False, False, 0)

        self.temp_labels[key] = {"value": value_label, "device_getter": device_getter}
        return card

    def _refresh_distance_buttons(self):
        for key, button in self.distance_buttons.items():
            ctx = button.get_style_context()
            if key == self.distance:
                ctx.add_class("workcell-distance-button-active")
            else:
                ctx.remove_class("workcell-distance-button-active")

    def set_distance(self, widget, distance):
        self.distance = distance
        self._refresh_distance_buttons()

    def move_axis(self, widget, axis, direction):
        if self.motion_locked:
            self._screen.show_popup_message(_("Motion is disabled while printing"))
            return

        axis_lower = axis.lower()
        if axis_lower != "z" and self._config.get_config()["main"].getboolean(f"invert_{axis_lower}", False):
            direction = "-" if direction == "+" else "+"

        distance = f"{direction}{self.distance}"
        config_key = "move_speed_z" if axis_lower == "z" else "move_speed_xy"
        speed = None if self.ks_printer_cfg is None else self.ks_printer_cfg.getint(config_key, None)
        if speed is None:
            printer_cfg = self._printer.get_config_section("printer")
            speed = int(float(printer_cfg.get("max_z_velocity" if axis_lower == "z" else "max_velocity", "10")))
        feedrate = 60 * max(1, speed)

        script = f"{KlippyGcodes.MOVE_RELATIVE}\nG0 {axis}{distance} F{feedrate}"
        self._screen._send_action(widget, "printer.gcode.script", {"script": script})
        if self._printer.get_stat("gcode_move", "absolute_coordinates"):
            self._screen._ws.klippy.gcode_script("G90")

    def home_axes(self, widget):
        if self.motion_locked:
            self._screen.show_popup_message(_("Motion is disabled while printing"))
            return
        self._screen._send_action(widget, "printer.gcode.script", {"script": "G28"})

    def adjust_temp(self, widget, key, delta, device_getter):
        device = device_getter()
        if not device:
            return

        target = self._printer.get_stat(device, "target")
        if target is None:
            target = self._printer.get_stat(device, "temperature") or 0
        new_target = max(0, int(round(float(target) + delta)))
        new_target = self._verify_max_temp(device, new_target)
        if new_target is False:
            return

        if device.startswith("extruder"):
            self._screen._ws.klippy.set_tool_temp(self._printer.get_tool_number(device), new_target)
        elif device == "heater_bed":
            self._screen._ws.klippy.set_bed_temp(new_target)
        elif device.startswith("heater_generic "):
            self._screen._ws.klippy.set_heater_temp(device.split(" ", maxsplit=1)[1], new_target)
        elif device.startswith("temperature_fan "):
            self._screen._ws.klippy.set_temp_fan_temp(device.split(" ", maxsplit=1)[1], new_target)
        else:
            script = {"script": f"SET_HEATER_TEMPERATURE HEATER={device} TARGET={new_target}"}
            self._screen._send_action(widget, "printer.gcode.script", script)

        name = device.split(" ", maxsplit=1)[-1]
        self._printer.set_stat(name, {"target": new_target})
        self.update_temp_controls()

    def _verify_max_temp(self, device, target):
        try:
            max_temp = int(float(self._printer.get_config_section(device)["max_temp"]))
        except Exception:
            return target
        if target > max_temp:
            self._screen.show_popup_message(_("Can't set above the maximum:") + f" {max_temp}")
            return False
        return target

    def update_temp_controls(self):
        current_extruder = self._printer.get_stat("toolhead", "extruder")
        if current_extruder:
            self.current_extruder = current_extruder

        for card in self.temp_labels.values():
            device = card["device_getter"]()
            temp = self._printer.get_stat(device, "temperature") if device else None
            card["value"].set_label(f"{temp:.0f}°" if temp is not None else "--°")

    def update_motion_lock(self):
        self.motion_locked = self._printer.get_stat("print_stats", "state") == "printing"
        for button in self.motion_buttons:
            button.set_sensitive(not self.motion_locked)

    def _safe_show_panel(self, panel_name):
        try:
            self._screen.show_panel(panel_name)
        except Exception as err:
            logging.debug(f"Unable to open panel '{panel_name}': {err}")
            self._screen.show_popup_message(_("Panel is not available"))

    def go_home(self, widget):
        self._screen._menu_go_back(home=True)

    def go_controls(self, widget):
        return

    def go_queue(self, widget):
        self._safe_show_panel("print_screen")

    def go_filament(self, widget):
        self._safe_show_panel("filament")

    def activate(self):
        self.update_temp_controls()
        self.update_motion_lock()

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        self.update_temp_controls()
        self.update_motion_lock()
