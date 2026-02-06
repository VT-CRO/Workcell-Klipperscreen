import logging
import os
import pathlib

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, GLib, Gtk

from ks_includes.widgets.keypad import Keypad
from panels.menu import Panel as MenuPanel


class Panel(MenuPanel):
    def __init__(self, screen, title, items=None):
        super().__init__(screen, title, items)
        self.content.get_style_context().add_class("workcell-bg")
        self.compact_mode = not self._screen.vertical_mode and self._screen.width <= 800 and self._screen.height <= 480

        styles_dir = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles")
        self.paths = {
            "brand": os.path.join(styles_dir, "crologo.svg"),
            "mark": os.path.join(styles_dir, "workcell-mark.svg"),
            "home": os.path.join(styles_dir, "home.svg"),
            "settings": os.path.join(styles_dir, "sliders.svg"),
            "files": os.path.join(styles_dir, "menu-bars.svg"),
            "spool": os.path.join(styles_dir, "spool.svg"),
            "temp_nozzle": os.path.join(styles_dir, "thermometer-nozzle.svg"),
            "temp_bed": os.path.join(styles_dir, "thermometer-bed.svg"),
        }

        self.active_heater = None
        self.numpad_visible = False
        self.temp_cards = {}

        self.overlay = Gtk.Overlay()
        self.content.add(self.overlay)

        root_orientation = Gtk.Orientation.VERTICAL if self._screen.vertical_mode else Gtk.Orientation.HORIZONTAL
        self.root = Gtk.Box(orientation=root_orientation, spacing=0)
        self.root.get_style_context().add_class("workcell-root")
        if self.compact_mode:
            self.root.get_style_context().add_class("workcell-compact")
        self.overlay.add(self.root)

        self.sidebar = self.create_sidebar()
        self.root.pack_start(self.sidebar, False, False, 0)

        self.main_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14 if self.compact_mode else 24)
        self.main_area.get_style_context().add_class("workcell-main-area")
        if self._screen.vertical_mode:
            self.main_area.set_margin_top(16)
            self.main_area.set_margin_start(16)
            self.main_area.set_margin_end(16)
            self.main_area.set_margin_bottom(16)
        else:
            if self.compact_mode:
                self.main_area.set_margin_top(8)
                self.main_area.set_margin_start(10)
                self.main_area.set_margin_end(10)
                self.main_area.set_margin_bottom(8)
            else:
                self.main_area.set_margin_top(24)
                self.main_area.set_margin_start(30)
                self.main_area.set_margin_end(30)
                self.main_area.set_margin_bottom(24)
        self.root.pack_start(self.main_area, True, True, 0)

        hero_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        hero_box.set_halign(Gtk.Align.CENTER)
        hero_box.set_valign(Gtk.Align.CENTER)
        hero_box.set_hexpand(True)
        hero_box.set_vexpand(True)
        if self._screen.vertical_mode:
            hero_size = min(int(self._screen.width * 0.62), 420)
        elif self.compact_mode:
            hero_size = min(int(self._screen.height * 0.52), 250)
        else:
            hero_size = min(int(self._screen.width * 0.52), 760)
        hero_image = self._image_from_file(self.paths["brand"], hero_size, hero_size)
        hero_image.get_style_context().add_class("workcell-hero-logo")
        hero_box.pack_start(hero_image, False, False, 0)
        self.main_area.pack_start(hero_box, True, True, 0)

        temp_orientation = Gtk.Orientation.VERTICAL if self._screen.vertical_mode else Gtk.Orientation.HORIZONTAL
        self.temp_row = Gtk.Box(orientation=temp_orientation, spacing=12 if self.compact_mode else 24)
        self.temp_row.get_style_context().add_class("workcell-temp-row")
        self.temp_row.set_hexpand(True)

        nozzle_device = self._printer.get_stat("toolhead", "extruder") or "extruder"
        self._build_temp_card(
            key="nozzle",
            label=_("Nozzle"),
            device=nozzle_device,
            icon_path=self.paths["temp_nozzle"],
            icon_style="workcell-temp-icon-nozzle",
        )
        self._build_temp_card(
            key="bed",
            label=_("Bed"),
            device="heater_bed",
            icon_path=self.paths["temp_bed"],
            icon_style="workcell-temp-icon-bed",
        )
        self.main_area.pack_end(self.temp_row, False, False, 0)

        self.numpad_placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.numpad_placeholder.get_style_context().add_class("workcell-numpad-overlay")
        self.numpad_placeholder.set_halign(Gtk.Align.FILL)
        self.numpad_placeholder.set_valign(Gtk.Align.FILL)
        self.numpad_placeholder.set_hexpand(True)
        self.numpad_placeholder.set_vexpand(True)
        self.numpad_placeholder.set_no_show_all(True)
        self.numpad_placeholder.hide()
        self.overlay.add_overlay(self.numpad_placeholder)
        self.overlay.set_overlay_pass_through(self.numpad_placeholder, True)

        self.update_temperatures()
        GLib.timeout_add_seconds(1, self.update_temperatures)

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
            sidebar.set_margin_top(10)
            sidebar.set_margin_start(10)
            sidebar.set_margin_end(10)
            sidebar.set_margin_bottom(10)
        else:
            sidebar_width = 92 if self.compact_mode else max(int(self._screen.width * 0.13), 130)
            sidebar.set_size_request(sidebar_width, -1)
            if self.compact_mode:
                sidebar.set_margin_top(6)
                sidebar.set_margin_start(6)
                sidebar.set_margin_end(6)
                sidebar.set_margin_bottom(6)
            else:
                sidebar.set_margin_top(12)
                sidebar.set_margin_start(10)
                sidebar.set_margin_end(10)
                sidebar.set_margin_bottom(12)

        if self._screen.vertical_mode:
            mark_size = 52
        elif self.compact_mode:
            mark_size = 42
        else:
            mark_size = 66
        mark = self._image_from_file(self.paths["mark"], mark_size, mark_size)
        mark.get_style_context().add_class("workcell-sidebar-mark")
        sidebar.pack_start(mark, False, False, 0)

        button_specs = [
            (self.paths["home"], self.go_home),
            (self.paths["settings"], self.go_settings),
            (self.paths["files"], self.go_files),
            (self.paths["spool"], self.go_spool),
        ]

        if self._screen.vertical_mode:
            button_size, icon_size = 76, 36
        elif self.compact_mode:
            button_size, icon_size = 64, 30
        else:
            button_size, icon_size = 96, 46
        for icon, callback in button_specs:
            button = Gtk.Button()
            button.get_style_context().add_class("workcell-nav-button")
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.set_size_request(button_size, button_size)
            button.add(self._image_from_file(icon, icon_size, icon_size))
            button.connect("clicked", callback)
            sidebar.pack_start(button, False, False, 0)

        return sidebar

    def _build_temp_card(self, key, label, device, icon_path, icon_style):
        button = Gtk.Button()
        button.get_style_context().add_class("workcell-temp-card")
        button.set_hexpand(True)
        button.connect("clicked", self.show_numpad, key)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10 if self.compact_mode else 16)
        if self.compact_mode:
            row.set_margin_top(8)
            row.set_margin_bottom(8)
            row.set_margin_start(12)
            row.set_margin_end(12)
        else:
            row.set_margin_top(14)
            row.set_margin_bottom(14)
            row.set_margin_start(18)
            row.set_margin_end(18)

        icon_size = 32 if self.compact_mode else 42
        icon = self._image_from_file(icon_path, icon_size, icon_size)
        icon.get_style_context().add_class(icon_style)
        row.pack_start(icon, False, False, 0)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)

        title_label = Gtk.Label(label=label, xalign=0)
        title_label.get_style_context().add_class("workcell-temp-title")

        value_label = Gtk.Label(label="--°", xalign=0)
        value_label.get_style_context().add_class("workcell-temp-value")

        text_box.pack_start(title_label, False, False, 0)
        text_box.pack_start(value_label, False, False, 0)

        state_label = Gtk.Label(label=_("Idle"), xalign=1)
        state_label.set_halign(Gtk.Align.END)
        state_label.get_style_context().add_class("workcell-temp-state")

        row.pack_start(text_box, True, True, 0)
        row.pack_end(state_label, False, False, 0)

        button.add(row)
        self.temp_row.pack_start(button, True, True, 0)

        self.temp_cards[key] = {
            "device": device,
            "value": value_label,
            "state": state_label,
        }

    def update_temperatures(self):
        current_extruder = self._printer.get_stat("toolhead", "extruder")
        if current_extruder and "nozzle" in self.temp_cards:
            self.temp_cards["nozzle"]["device"] = current_extruder

        for card in self.temp_cards.values():
            device = card["device"]
            current_temp = self._printer.get_stat(device, "temperature")
            target_temp = self._printer.get_stat(device, "target")

            value = f"{current_temp:.0f}°" if current_temp is not None else "--°"
            state = _("Printing") if target_temp and target_temp > 0 else _("Idle")

            card["value"].set_label(value)
            card["state"].set_label(state)
        return True

    def show_numpad(self, button, card_key):
        if card_key not in self.temp_cards:
            return

        self.active_heater = self.temp_cards[card_key]["device"]
        if not self.active_heater:
            return

        if "keypad" not in self.labels:
            self.labels["keypad"] = Keypad(self._screen, self.change_target_temp, self.pid_calibrate, self.hide_numpad)
            self.labels["label"] = Gtk.Label(xalign=0)
            self.labels["label"].get_style_context().add_class("workcell-numpad-title")
            self.labels["vbox"] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            self.labels["vbox"].get_style_context().add_class("workcell-numpad-container")

        can_pid = False
        if self._printer.state not in ("printing", "paused"):
            try:
                can_pid = self._screen.printer.config[self.active_heater]["control"] == "pid"
            except Exception:
                can_pid = False
        self.labels["keypad"].show_pid(can_pid)
        self.labels["keypad"].clear()

        heater_name = self.active_heater.replace("_", " ")
        self.labels["label"].set_label(_("Set {heater} temperature").format(heater=heater_name))

        for child in self.numpad_placeholder.get_children():
            self.numpad_placeholder.remove(child)

        if self.labels["keypad"].get_parent() is not None:
            self.labels["keypad"].get_parent().remove(self.labels["keypad"])
        if self.labels["label"].get_parent() is not None:
            self.labels["label"].get_parent().remove(self.labels["label"])

        self.labels["vbox"].pack_start(self.labels["label"], False, False, 0)
        self.labels["vbox"].pack_start(self.labels["keypad"], True, True, 0)
        self.numpad_placeholder.pack_start(self.labels["vbox"], True, True, 0)
        self.numpad_placeholder.set_no_show_all(False)
        self.overlay.set_overlay_pass_through(self.numpad_placeholder, False)
        self.numpad_placeholder.show_all()
        self.numpad_visible = True

    def hide_numpad(self, widget=None):
        for child in self.numpad_placeholder.get_children():
            self.numpad_placeholder.remove(child)
        self.numpad_placeholder.hide()
        self.numpad_placeholder.set_no_show_all(True)
        self.overlay.set_overlay_pass_through(self.numpad_placeholder, True)
        self.numpad_visible = False

    def change_target_temp(self, temp):
        if not self.active_heater:
            return

        name = self.active_heater.split()[1] if len(self.active_heater.split()) > 1 else self.active_heater
        temp = self.verify_max_temp(temp)
        if temp is False:
            return

        if self.active_heater.startswith("extruder"):
            self._screen._ws.klippy.set_tool_temp(self._printer.get_tool_number(self.active_heater), temp)
        elif self.active_heater == "heater_bed":
            self._screen._ws.klippy.set_bed_temp(temp)
        elif self.active_heater.startswith("heater_generic "):
            self._screen._ws.klippy.set_heater_temp(name, temp)
        elif self.active_heater.startswith("temperature_fan "):
            self._screen._ws.klippy.set_temp_fan_temp(name, temp)
        else:
            logging.info(f"Unknown heater: {self.active_heater}")
            self._screen.show_popup_message(_("Unknown Heater") + " " + self.active_heater)
        self._printer.set_stat(name, {"target": temp})

    def pid_calibrate(self, temp):
        if not self.active_heater:
            return

        heater = self.active_heater.split(" ", maxsplit=1)[-1]
        if self.verify_max_temp(temp):
            script = {"script": f"PID_CALIBRATE HEATER={heater} TARGET={temp}"}
            self._screen._confirm_send_action(
                None,
                _("Initiate a PID calibration for:")
                + f" {heater} @ {temp} ºC"
                + "\n\n"
                + _("It may take more than 5 minutes depending on the heater power."),
                "printer.gcode.script",
                script,
            )

    def verify_max_temp(self, temp):
        temp = int(temp)
        try:
            max_temp = int(float(self._printer.get_config_section(self.active_heater)["max_temp"]))
        except Exception:
            return max(temp, 0)
        logging.debug(f"{temp}/{max_temp}")
        if temp > max_temp:
            self._screen.show_popup_message(_("Can't set above the maximum:") + f" {max_temp}")
            return False
        return max(temp, 0)

    def go_home(self, button):
        self._screen._menu_go_back(home=True)

    def go_settings(self, button):
        self._screen.show_panel("settings")

    def go_files(self, button):
        self._screen.show_panel("print_screen")

    def go_spool(self, button):
        try:
            self._screen.show_panel("spoolman")
        except Exception as err:
            logging.debug(f"Unable to open spoolman panel: {err}")
            self._screen.show_popup_message(_("Spool panel is not available"))

    def back(self):
        if self.numpad_visible:
            self.hide_numpad()
            return True
        return super().back()

    def activate(self):
        self.update_temperatures()
