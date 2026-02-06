# -*- coding: utf-8 -*-
import logging
import os
import pathlib

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, GdkPixbuf, Gtk, Pango
from math import pi, sqrt, trunc
from statistics import median
from time import time

from ks_includes.KlippyGtk import find_widget
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Job Status")
        super().__init__(screen, title)

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
            "preview": os.path.join(styles_dir, "cube-placeholder.svg"),
        }

        self.thumb_dialog = None
        self.pos_z = 0.0
        self.extrusion = 100
        self.speed_factor = 1.0
        self.speed = 100
        self.req_speed = 0
        self.oheight = 0.0
        self.current_extruder = None
        self.fila_section = pi * ((1.75 / 2) ** 2)
        self.filename_label = {"complete": "Filename", "current": "Filename"}
        self.filename = ""
        self.prev_pos = None
        self.prev_gpos = None
        self.can_close = False
        self.flow_timeout = None
        self.animation_timeout = None
        self.file_metadata = {}
        self.fans = {}
        self.state = "standby"
        self.timeleft_type = "auto"
        self.progress = 0.0
        self.zoffset = 0.0
        self.flowrate = 0.0
        self.vel = 0.0
        self.flowstore = []
        self.mm = _("mm")
        self.mms = _("mm/s")
        self.mms2 = _("mm/s²")
        self.mms3 = _("mm³/s")
        self.status_grid = None
        self.move_grid = None
        self.time_grid = None
        self.extrusion_grid = None

        data = [
            "pos_x", "pos_y", "pos_z", "time_left", "duration", "slicer_time", "file_time",
            "filament_time", "est_time", "speed_factor", "req_speed", "max_accel", "extrude_factor", "zoffset",
            "zoffset", "filament_used", "filament_total", "advance", "layer", "total_layers", "height",
            "flowrate"
        ]

        for item in data:
            self.labels[item] = Gtk.Label(label="-", hexpand=True, vexpand=True)

        self.labels["left"] = Gtk.Label(_("Left:"))
        self.labels["elapsed"] = Gtk.Label(_("Elapsed:"))
        self.labels["total"] = Gtk.Label(_("Total:"))
        self.labels["slicer"] = Gtk.Label(_("Slicer:"))
        self.labels["file_tlbl"] = Gtk.Label(_("File:"))
        self.labels["fila_tlbl"] = Gtk.Label(_("Filament:"))
        self.labels["speed_lbl"] = Gtk.Label(_("Speed:"))
        self.labels["accel_lbl"] = Gtk.Label(_("Acceleration:"))
        self.labels["flow"] = Gtk.Label(_("Flow:"))
        self.labels["zoffset_lbl"] = Gtk.Label(_("Z offset:"))
        self.labels["fila_used_lbl"] = Gtk.Label(_("Filament used:"))
        self.labels["fila_total_lbl"] = Gtk.Label(_("Filament total:"))
        self.labels["pa_lbl"] = Gtk.Label(_("Pressure Advance:"))
        self.labels["flowrate_lbl"] = Gtk.Label(_("Flowrate:"))
        self.labels["height_lbl"] = Gtk.Label(_("Height:"))
        self.labels["layer_lbl"] = Gtk.Label(_("Layer:"))

        self.labels["file"] = Gtk.Label(label=_("No file"))
        self.labels["file"].set_halign(Gtk.Align.START)
        self.labels["file"].set_ellipsize(Pango.EllipsizeMode.END)
        self.labels["file"].get_style_context().add_class("workcell-job-filename")

        self.labels["author"] = Gtk.Label(label=_("Author Name"))
        self.labels["author"].set_halign(Gtk.Align.START)
        self.labels["author"].set_ellipsize(Pango.EllipsizeMode.END)
        self.labels["author"].get_style_context().add_class("workcell-job-author")

        self.labels["lcdmessage"] = Gtk.Label(no_show_all=True)
        self.labels["lcdmessage"].get_style_context().add_class("printing-status")

        for label in self.labels.values():
            if isinstance(label, Gtk.Label):
                label.set_ellipsize(Pango.EllipsizeMode.END)

        root_orientation = Gtk.Orientation.VERTICAL if self._screen.vertical_mode else Gtk.Orientation.HORIZONTAL
        self.layout = Gtk.Box(orientation=root_orientation, spacing=0)
        self.layout.get_style_context().add_class("workcell-root")
        if self.compact_mode:
            self.layout.get_style_context().add_class("workcell-compact")
        self.content.add(self.layout)

        self.sidebar = self.create_sidebar()
        self.layout.pack_start(self.sidebar, False, False, 0)

        self.main_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14 if self.compact_mode else 24)
        self.main_area.get_style_context().add_class("workcell-main-area")
        if self._screen.vertical_mode:
            self.main_area.set_margin_top(14)
            self.main_area.set_margin_start(14)
            self.main_area.set_margin_end(14)
            self.main_area.set_margin_bottom(14)
        else:
            if self.compact_mode:
                self.main_area.set_margin_top(8)
                self.main_area.set_margin_start(10)
                self.main_area.set_margin_end(10)
                self.main_area.set_margin_bottom(8)
            else:
                self.main_area.set_margin_top(22)
                self.main_area.set_margin_start(24)
                self.main_area.set_margin_end(24)
                self.main_area.set_margin_bottom(20)
        self.layout.pack_start(self.main_area, True, True, 0)

        top_orientation = Gtk.Orientation.VERTICAL if self._screen.vertical_mode else Gtk.Orientation.HORIZONTAL
        self.top_row = Gtk.Box(orientation=top_orientation, spacing=14 if self.compact_mode else 24)
        self.top_row.get_style_context().add_class("workcell-job-top")
        self.main_area.pack_start(self.top_row, True, True, 0)

        self.labels["thumbnail"] = Gtk.Button()
        self.labels["thumbnail"].get_style_context().add_class("workcell-thumbnail-button")
        self.labels["thumbnail"].set_hexpand(True)
        self.labels["thumbnail"].set_vexpand(True)
        self.labels["thumbnail"].connect("clicked", self.show_fullscreen_thumbnail)
        preview_w = 290 if self.compact_mode else 420
        preview_h = 210 if self.compact_mode else 330
        self.labels["thumbnail"].add(self._image_from_file(self.paths["preview"], preview_w, preview_h))
        self.top_row.pack_start(self.labels["thumbnail"], True, True, 0)

        status_pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10 if self.compact_mode else 14)
        status_pane.get_style_context().add_class("workcell-status-pane")
        status_pane.set_hexpand(True)
        self.top_row.pack_start(status_pane, True, True, 0)

        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8 if self.compact_mode else 12)
        header_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        header_text.set_hexpand(True)
        header_text.pack_start(self.labels["file"], False, False, 0)
        header_text.pack_start(self.labels["author"], False, False, 0)
        header_row.pack_start(header_text, True, True, 0)

        if self._screen.vertical_mode:
            brand_size = 46
        elif self.compact_mode:
            brand_size = 42
        else:
            brand_size = 64
        brand_icon = self._image_from_file(self.paths["brand"], brand_size, brand_size)
        brand_icon.get_style_context().add_class("workcell-job-brand")
        header_row.pack_end(brand_icon, False, False, 0)
        status_pane.pack_start(header_row, False, False, 0)

        self.buttons = {}
        self.create_buttons()
        self.buttons["button_box"] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8 if self.compact_mode else 12)
        status_pane.pack_start(self.buttons["button_box"], False, False, 0)

        progress_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        progress_row.set_hexpand(True)

        self.labels["progress_text"] = Gtk.Label(label="0%")
        self.labels["progress_text"].get_style_context().add_class("workcell-progress-percent")

        self.labels["remaining_time"] = Gtk.Label(label="0h 00m")
        self.labels["remaining_time"].set_halign(Gtk.Align.END)
        self.labels["remaining_time"].get_style_context().add_class("workcell-progress-time")

        progress_row.pack_start(self.labels["progress_text"], False, False, 0)
        progress_row.pack_end(self.labels["remaining_time"], False, False, 0)
        status_pane.pack_start(progress_row, False, False, 0)

        self.labels["darea"] = Gtk.DrawingArea()
        self.labels["darea"].connect("draw", self.on_draw)
        self.labels["darea"].set_size_request(-1, 8 if self.compact_mode else 10)
        self.labels["darea"].get_style_context().add_class("workcell-progress-bar")
        status_pane.pack_start(self.labels["darea"], False, False, 0)

        self.labels["progress_detail"] = Gtk.Label(label="0 / 0")
        self.labels["progress_detail"].set_halign(Gtk.Align.START)
        self.labels["progress_detail"].get_style_context().add_class("workcell-progress-detail")
        status_pane.pack_start(self.labels["progress_detail"], False, False, 0)

        self.temp_row = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL if self._screen.vertical_mode else Gtk.Orientation.HORIZONTAL,
            spacing=12 if self.compact_mode else 24,
        )
        self.temp_row.get_style_context().add_class("workcell-temp-row")
        self.temp_row.set_hexpand(True)
        self.main_area.pack_end(self.temp_row, False, False, 0)

        self.current_extruder = self._printer.get_stat("toolhead", "extruder") or "extruder"
        if self.current_extruder:
            try:
                diameter = float(self._printer.get_config_section(self.current_extruder)["filament_diameter"])
                self.fila_section = pi * ((diameter / 2) ** 2)
            except Exception:
                pass

        self.temp_cards = {}
        self._build_temperature_card("nozzle", _("Nozzle"), self.current_extruder, self.paths["temp_nozzle"])
        self._build_temperature_card("bed", _("Bed"), "heater_bed", self.paths["temp_bed"])

        self.update_temperature_cards()
        self.show_buttons_for_state()
        self.content.show_all()

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

        if self._screen.vertical_mode:
            mark_size = 52
        elif self.compact_mode:
            mark_size = 42
        else:
            mark_size = 66
        sidebar.pack_start(self._image_from_file(self.paths["mark"], mark_size, mark_size), False, False, 0)

        if self._screen.vertical_mode:
            button_size, icon_size = 76, 36
        elif self.compact_mode:
            button_size, icon_size = 64, 30
        else:
            button_size, icon_size = 96, 46
        sidebar.pack_start(self._nav_button(self.paths["home"], button_size, icon_size, self.go_home), False, False, 0)
        sidebar.pack_start(
            self._nav_button(self.paths["settings"], button_size, icon_size, self.go_settings), False, False, 0
        )
        sidebar.pack_start(self._nav_button(self.paths["files"], button_size, icon_size, self.go_files), False, False, 0)
        sidebar.pack_start(self._nav_button(self.paths["spool"], button_size, icon_size, self.go_spool), False, False, 0)

        return sidebar

    def _nav_button(self, icon_path, button_size, icon_size, callback):
        button = Gtk.Button()
        button.get_style_context().add_class("workcell-nav-button")
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.set_size_request(button_size, button_size)
        button.add(self._image_from_file(icon_path, icon_size, icon_size))
        button.connect("clicked", callback)
        return button

    def _safe_show_panel(self, panel_name):
        try:
            self._screen.show_panel(panel_name)
        except Exception as err:
            logging.debug(f"Unable to open panel '{panel_name}': {err}")
            self._screen.show_popup_message(_("Panel is not available"))

    def go_home(self, button):
        self._screen._menu_go_back(home=True)

    def go_settings(self, button):
        self._safe_show_panel("settings")

    def go_files(self, button):
        self._safe_show_panel("print_screen")

    def go_spool(self, button):
        self._safe_show_panel("spoolman")

    def _build_temperature_card(self, key, label, device, icon_path):
        card = Gtk.EventBox()
        card.get_style_context().add_class("workcell-temp-card")

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
        icon_class = "workcell-temp-icon-nozzle" if key == "nozzle" else "workcell-temp-icon-bed"
        icon.get_style_context().add_class(icon_class)
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

        card.add(row)
        self.temp_row.pack_start(card, True, True, 0)

        self.temp_cards[key] = {
            "device": device,
            "value": value_label,
            "state": state_label,
        }

    def update_temperature_cards(self):
        if "nozzle" in self.temp_cards and self.current_extruder:
            self.temp_cards["nozzle"]["device"] = self.current_extruder

        for card in self.temp_cards.values():
            device = card["device"]
            current_temp = self._printer.get_stat(device, "temperature")
            target_temp = self._printer.get_stat(device, "target")
            value = f"{current_temp:.0f}°" if current_temp is not None else "--°"
            state = _("Printing") if self.state in {"printing", "paused"} or (target_temp and target_temp > 0) else _("Idle")
            card["value"].set_label(value)
            card["state"].set_label(state)

    def update_temp(self, dev, temp, target, power, lines=1, digits=1):
        super().update_temp(dev, temp, target, power, lines=lines, digits=digits)

        for card in self.temp_cards.values():
            if card["device"] != dev:
                continue
            value = f"{temp:.0f}°" if temp is not None else "--°"
            state = _("Printing") if self.state in {"printing", "paused"} or (target and target > 0) else _("Idle")
            card["value"].set_label(value)
            card["state"].set_label(state)

    @staticmethod
    def format_compact_time(seconds):
        if seconds is None or seconds <= 0:
            return "-"

        total_minutes = int(round(seconds / 60))
        days = total_minutes // (24 * 60)
        hours = (total_minutes % (24 * 60)) // 60
        minutes = total_minutes % 60

        if days > 0:
            return f"{days}d {hours:02d}h"
        if hours > 0:
            return f"{hours}h {minutes:02d}m"
        return f"{minutes}m"
    def create_status_grid(self, widget=None):
        # buttons = {
        #     'speed': self._gtk.Button("speed+", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
        #     'z': self._gtk.Button("home-z", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
        #     'extrusion': self._gtk.Button("extrude", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
        #     'fan': self._gtk.Button("fan", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
        #     'elapsed': self._gtk.Button("clock", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
        #     'left': self._gtk.Button("hourglass", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
        # }
        
        buttons = {
            'elapsed': self._gtk.Button("clock", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
            'left': self._gtk.Button("hourglass", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
        }
        
        for button in buttons:
            buttons[button].set_halign(Gtk.Align.START)
        self.buttons.update(buttons)

        szfe = Gtk.Grid(column_homogeneous=True)

        info = Gtk.Grid(row_homogeneous=True)
        # File Name
        fi_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, halign=Gtk.Align.START)
        fi_box.add(Gtk.Label(label="  Filename: "))
        fi_box.add(self.labels['file'])
        info.attach(fi_box,0,0,1,1)
        # info.get_style_context().add_class("printing-info")
        info.attach(szfe, 0, 1, 1, 2)
        info.attach(self.buttons['elapsed'], 0, 1, 1, 1)
        info.attach(self.buttons['left'], 0, 2, 1, 1)
        self.status_grid = info

    def create_extrusion_grid(self, widget=None):
        goback = self._gtk.Button("back", None, "color1", self.bts, Gtk.PositionType.TOP, False)
        goback.connect("clicked", self.switch_info, self.status_grid)
        goback.set_hexpand(False)
        goback.get_style_context().add_class("printing-info")

        info = Gtk.Grid(hexpand=True, vexpand=True, halign=Gtk.Align.START)
        info.get_style_context().add_class("printing-info-secondary")
        info.attach(goback, 0, 0, 1, 6)
        info.attach(self.labels['flow'], 1, 0, 1, 1)
        info.attach(self.labels['extrude_factor'], 2, 0, 1, 1)
        info.attach(self.labels['flowrate_lbl'], 1, 1, 1, 1)
        info.attach(self.labels['flowrate'], 2, 1, 1, 1)
        info.attach(self.labels['pa_lbl'], 1, 2, 1, 1)
        info.attach(self.labels['advance'], 2, 2, 1, 1)
        info.attach(self.labels['fila_used_lbl'], 1, 3, 1, 1)
        info.attach(self.labels['filament_used'], 2, 3, 1, 1)
        info.attach(self.labels['fila_total_lbl'], 1, 4, 1, 1)
        info.attach(self.labels['filament_total'], 2, 4, 1, 1)
        self.extrusion_grid = info
        self.buttons['extrusion'].connect("clicked", self.switch_info, self.extrusion_grid)
        

    def create_move_grid(self, widget=None):
        goback = self._gtk.Button("back", None, "color2", self.bts, Gtk.PositionType.TOP, False)
        goback.connect("clicked", self.switch_info, self.status_grid)
        goback.set_hexpand(False)
        goback.get_style_context().add_class("printing-info")

        pos_box = Gtk.Box(spacing=5)
        pos_box.add(self.labels['pos_x'])
        pos_box.add(self.labels['pos_y'])
        pos_box.add(self.labels['pos_z'])

        info = Gtk.Grid(hexpand=True, vexpand=True, halign=Gtk.Align.START)
        info.get_style_context().add_class("printing-info-secondary")
        info.attach(goback, 0, 0, 1, 6)
        info.attach(self.labels['speed_lbl'], 1, 0, 1, 1)
        info.attach(self.labels['req_speed'], 2, 0, 1, 1)
        info.attach(self.labels['accel_lbl'], 1, 1, 1, 1)
        info.attach(self.labels['max_accel'], 2, 1, 1, 1)
        info.attach(pos_box, 1, 2, 2, 1)
        info.attach(self.labels['zoffset_lbl'], 1, 3, 1, 1)
        info.attach(self.labels['zoffset'], 2, 3, 1, 1)
        info.attach(self.labels['height_lbl'], 1, 4, 1, 1)
        info.attach(self.labels['height'], 2, 4, 1, 1)
        info.attach(self.labels['layer_lbl'], 1, 5, 1, 1)
        info.attach(self.labels['layer'], 2, 5, 1, 1)
        self.move_grid = info

    def create_time_grid(self, widget=None):
        goback = self._gtk.Button("back", None, "color3", self.bts, Gtk.PositionType.TOP, False)
        goback.connect("clicked", self.switch_info, self.status_grid)
        goback.set_hexpand(False)

        info = Gtk.Grid()
        info.get_style_context().add_class("printing-info-secondary")
        info.attach(goback, 0, 0, 1, 6)
        info.attach(self.labels['elapsed'], 1, 0, 1, 1)
        info.attach(self.labels['duration'], 2, 0, 1, 1)
        info.attach(self.labels['left'], 1, 1, 1, 1)
        info.attach(self.labels['time_left'], 2, 1, 1, 1)
        info.attach(self.labels['total'], 1, 2, 1, 1)
        info.attach(self.labels['est_time'], 2, 2, 1, 1)
        info.attach(self.labels['slicer'], 1, 3, 1, 1)
        info.attach(self.labels['slicer_time'], 2, 3, 1, 1)
        info.attach(self.labels['file_tlbl'], 1, 4, 1, 1)
        info.attach(self.labels['file_time'], 2, 4, 1, 1)
        info.attach(self.labels['fila_tlbl'], 1, 5, 1, 1)
        info.attach(self.labels['filament_time'], 2, 5, 1, 1)
        self.time_grid = info
        self.buttons['elapsed'].connect("clicked", self.switch_info, self.time_grid)
        self.buttons['left'].connect("clicked", self.switch_info, self.time_grid)

    def switch_info(self, widget=None, info=None):
        if not info:
            logging.debug("No info to attach")
            return
        if self._screen.vertical_mode:
            self.labels['info_grid'].remove_row(1)
            self.labels['info_grid'].attach(info, 0, 1, 1, 1)
        else:
            self.labels['info_grid'].remove_column(1)
            self.labels['info_grid'].attach(info, 1, 0, 1, 1)
            pass
        self.labels['info_grid'].show_all()

    def on_draw(self, da, ctx):
        width = max(da.get_allocated_width(), 1)
        height = max(da.get_allocated_height(), 1)
        radius = height / 2

        def rounded_rect(x, y, w, h, r):
            r = min(r, w / 2, h / 2)
            ctx.new_sub_path()
            ctx.arc(x + w - r, y + r, r, -pi / 2, 0)
            ctx.arc(x + w - r, y + h - r, r, 0, pi / 2)
            ctx.arc(x + r, y + h - r, r, pi / 2, pi)
            ctx.arc(x + r, y + r, r, pi, 3 * pi / 2)
            ctx.close_path()

        rounded_rect(0, 0, width, height, radius)
        ctx.set_source_rgb(0.17, 0.18, 0.20)
        ctx.fill()

        filled_width = max(min(width * self.progress, width), 0)
        if filled_width > 0:
            rounded_rect(0, 0, filled_width, height, radius)
            ctx.set_source_rgb(0.77, 0.02, 0.02)
            ctx.fill()

        return True

    def activate(self):
        if self.flow_timeout is None:
            self.flow_timeout = GLib.timeout_add_seconds(2, self.update_flow)
        if self.animation_timeout is None:
            self.animation_timeout = GLib.timeout_add(500, self.animate_label)

    def deactivate(self):
        if self.flow_timeout is not None:
            GLib.source_remove(self.flow_timeout)
            self.flow_timeout = None
        if self.animation_timeout is not None:
            GLib.source_remove(self.animation_timeout)
            self.animation_timeout = None

    def create_buttons(self):
        self.buttons = {
            'cancel': self.create_rounded_button("cancel", _("Cancel"), self.cancel, danger=True),
            'menu': self.create_rounded_button("home", _("Main Menu"), self.close_panel),
            'pause': self.create_rounded_button("pause", _("Pause"), self.pause),
            'restart': self.create_rounded_button("refresh", _("Restart"), self.restart),
            'resume': self.create_rounded_button("resume", _("Resume"), self.resume),
            'save_offset_probe': self._gtk.Button("home-z", _("Save Z") + "\n" + "Probe", "color1"),
            'save_offset_endstop': self._gtk.Button("home-z", _("Save Z") + "\n" + "Endstop", "color2"),
        }
        self.buttons['save_offset_probe'].connect("clicked", self.save_offset, "probe")
        self.buttons['save_offset_endstop'].connect("clicked", self.save_offset, "endstop")
        
    def create_rounded_button(self, icon_name, label_text, callback, danger=False):
        button = Gtk.Button()
        button.get_style_context().add_class("workcell-action-button")
        if danger:
            button.get_style_context().add_class("workcell-action-danger")

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10 if self.compact_mode else 16)
        if self.compact_mode:
            row.set_margin_top(7)
            row.set_margin_bottom(7)
            row.set_margin_start(10)
            row.set_margin_end(10)
        else:
            row.set_margin_top(10)
            row.set_margin_bottom(10)
            row.set_margin_start(16)
            row.set_margin_end(16)

        if icon_name:
            scale = 0.85 if self.compact_mode else 1.1
            icon_size = int(self.bts * self._gtk.img_scale * scale)
            row.pack_start(self._gtk.Image(icon_name, icon_size, icon_size), False, False, 0)

        label = Gtk.Label(label=label_text)
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        label.get_style_context().add_class("workcell-action-label")
        row.pack_start(label, True, True, 0)

        button.add(row)
        button.connect("clicked", callback)
        return button

    def save_offset(self, widget, device):
        sign = "+" if self.zoffset > 0 else "-"
        label = Gtk.Label(hexpand=True, vexpand=True, wrap=True)
        saved_z_offset = None
        msg = f"Apply {sign}{abs(self.zoffset)} offset to {device}?"
        if device == "probe":
            msg = _("Apply %s%.3f offset to Probe?") % (sign, abs(self.zoffset))
            if probe := self._printer.get_probe():
                saved_z_offset = probe['z_offset']
        elif device == "endstop":
            msg = _("Apply %s%.3f offset to Endstop?") % (sign, abs(self.zoffset))
            if 'stepper_z' in self._printer.get_config_section_list():
                saved_z_offset = self._printer.get_config_section('stepper_z')['position_endstop']
            elif 'stepper_a' in self._printer.get_config_section_list():
                saved_z_offset = self._printer.get_config_section('stepper_a')['position_endstop']
        if saved_z_offset:
            msg += "\n\n" + _("Saved offset: %s") % saved_z_offset
        label.set_label(msg)
        buttons = [
            {"name": _("Apply"), "response": Gtk.ResponseType.APPLY, "style": 'dialog-default'},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": 'dialog-error'}
        ]
        self._gtk.Dialog(_("Save Z"), buttons, label, self.save_confirm, device)

    def save_confirm(self, dialog, response_id, device):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.APPLY:
            if device == "probe":
                self._screen._ws.klippy.gcode_script("Z_OFFSET_APPLY_PROBE")
            if device == "endstop":
                self._screen._ws.klippy.gcode_script("Z_OFFSET_APPLY_ENDSTOP")
            self._screen._ws.klippy.gcode_script("SAVE_CONFIG")

    def restart(self, widget):
        if self.filename:
            self.disable_button("restart")
            if self.state == "error":
                self._screen._ws.klippy.gcode_script("SDCARD_RESET_FILE")
            self._screen._ws.klippy.print_start(self.filename)
            logging.info(f"Starting print: {self.filename}")
            self.new_print()
        else:
            logging.info(f"Could not restart {self.filename}")

    def resume(self, widget):
        self._screen._ws.klippy.print_resume()
        self._screen.show_all()

    def pause(self, widget):
        self.disable_button("pause", "resume")
        self._screen._ws.klippy.print_pause()
        self._screen.show_all()

    def cancel(self, widget):
        buttons = [
            {"name": _("Cancel Print"), "response": Gtk.ResponseType.OK, "style": 'dialog-error'},
            {"name": _("Go Back"), "response": Gtk.ResponseType.CANCEL, "style": 'dialog-info'}
        ]
        if len(self._printer.get_stat("exclude_object", "objects")) > 1:
            buttons.insert(0, {"name": _("Exclude Object"), "response": Gtk.ResponseType.APPLY})
        label = Gtk.Label(hexpand=True, vexpand=True, wrap=True)
        label.set_markup(_("Are you sure you wish to cancel this print?"))
        self._gtk.Dialog(_("Cancel"), buttons, label, self.cancel_confirm)

    def cancel_confirm(self, dialog, response_id):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.APPLY:
            self.menu_item_clicked(None, {"panel": "exclude"})
            return
        if response_id == Gtk.ResponseType.CANCEL:
            self.enable_button("pause", "cancel")
            return
        logging.debug("Canceling print")
        self.set_state("cancelling")
        self.disable_button("pause", "resume", "cancel")
        self._screen._ws.klippy.print_cancel()

    def close_panel(self, widget=None):
        if self.can_close:
            logging.debug("Closing job_status panel")
            self._screen.state_ready(wait=False)

    def enable_button(self, *args):
        for arg in args:
            self.buttons[arg].set_sensitive(True)

    def disable_button(self, *args):
        for arg in args:
            self.buttons[arg].set_sensitive(False)

    def new_print(self):
        self._screen.screensaver.close()
        if "virtual_sdcard" in self._printer.data:
            logging.info("reseting progress")
            self._printer.data["virtual_sdcard"]["progress"] = 0
        self.update_progress(0.0)
        self.set_state("printing")

    def process_update(self, action, data):
        if action == "notify_gcode_response":
            if "action:cancel" in data:
                self.set_state("cancelled")
            elif "action:paused" in data:
                self.set_state("paused")
            elif "action:resumed" in data:
                self.set_state("printing")
            return
        elif action == "notify_metadata_update" and data['filename'] == self.filename:
            self.get_file_metadata(response=True)
        elif action != "notify_status_update":
            return

        for x in self._printer.get_temp_devices():
            if x in data:
                self.update_temp(
                    x,
                    self._printer.get_stat(x, "temperature"),
                    self._printer.get_stat(x, "target"),
                    self._printer.get_stat(x, "power"),
                    digits=0
                )
                # if x in self.buttons['extruder']:
                #     self.buttons['extruder'][x].set_label(self.labels[x].get_text())
                # elif x in self.buttons['heater']:
                #     self.buttons['heater'][x].set_label(self.labels[x].get_text())

        if "display_status" in data and "message" in data["display_status"]:
            if data['display_status']['message']:
                self.labels['lcdmessage'].set_label(f"{data['display_status']['message']}")
                self.labels['lcdmessage'].show()
            else:
                self.labels['lcdmessage'].hide()

        if 'toolhead' in data:
            if 'extruder' in data['toolhead'] and data['toolhead']['extruder']:
                self.current_extruder = data["toolhead"]["extruder"]
                if "nozzle" in self.temp_cards:
                    self.temp_cards["nozzle"]["device"] = self.current_extruder
            if "max_accel" in data["toolhead"]:
                self.labels['max_accel'].set_label(f"{data['toolhead']['max_accel']:.0f} {self.mms2}")
        if 'extruder' in data and 'pressure_advance' in data['extruder']:
            self.labels['advance'].set_label(f"{data['extruder']['pressure_advance']:.2f}")

        if 'gcode_move' in data:
            if 'gcode_position' in data['gcode_move']:
                self.pos_z = round(float(data['gcode_move']['gcode_position'][2]), 2)
            if 'extrude_factor' in data['gcode_move']:
                self.extrusion = round(float(data['gcode_move']['extrude_factor']) * 100)
                self.labels['extrude_factor'].set_label(f"{self.extrusion:3}%")
            if 'speed_factor' in data['gcode_move']:
                self.speed = round(float(data['gcode_move']['speed_factor']) * 100)
                self.speed_factor = float(data['gcode_move']['speed_factor'])
                self.labels['speed_factor'].set_label(f"{self.speed:3}%")
            if 'homing_origin' in data['gcode_move']:
                self.zoffset = float(data['gcode_move']['homing_origin'][2])
                self.labels['zoffset'].set_label(f"{self.zoffset:.3f} {self.mm}")
        if 'motion_report' in data:
            if 'live_position' in data['motion_report']:
                self.labels['pos_x'].set_label(f"X: {data['motion_report']['live_position'][0]:6.2f}")
                self.labels['pos_y'].set_label(f"Y: {data['motion_report']['live_position'][1]:6.2f}")
                self.labels['pos_z'].set_label(f"Z: {data['motion_report']['live_position'][2]:6.2f}")
                pos = data["motion_report"]["live_position"]
                now = time()
                if self.prev_pos is not None:
                    interval = (now - self.prev_pos[1])
                    # Calculate Flowrate
                    evelocity = (pos[3] - self.prev_pos[0][3]) / interval
                    self.flowstore.append(self.fila_section * evelocity)
                self.prev_pos = [pos, now]
            if 'live_velocity' in data['motion_report']:
                self.vel = float(data["motion_report"]["live_velocity"])
                self.labels['req_speed'].set_label(
                    f"{self.speed}% {self.vel:3.0f}/{self.req_speed:3.0f} "
                    f"{f'{self.mms}' if self.vel < 1000 and self.req_speed < 1000 and self._screen.width > 500 else ''}"
                )
            if 'live_extruder_velocity' in data['motion_report']:
                self.flowstore.append(self.fila_section * float(data["motion_report"]["live_extruder_velocity"]))
        if "print_stats" in data:
            if 'state' in data['print_stats']:
                self.set_state(
                    data["print_stats"]["state"],
                    msg=f'{data["print_stats"]["message"] if "message" in data["print_stats"] else ""}'
                )
            if 'filename' in data['print_stats']:
                self.update_filename(data['print_stats']["filename"])
            if 'filament_used' in data['print_stats']:
                self.labels['filament_used'].set_label(
                    f"{float(data['print_stats']['filament_used']) / 1000:.1f} m"
                )
            if 'info' in data["print_stats"]:
                if ('total_layer' in data['print_stats']['info']
                        and data["print_stats"]['info']['total_layer'] is not None):
                    self.labels['total_layers'].set_label(f"{data['print_stats']['info']['total_layer']}")
                if ('current_layer' in data['print_stats']['info']
                        and data['print_stats']['info']['current_layer'] is not None):
                    self.labels['layer'].set_label(
                        f"{data['print_stats']['info']['current_layer']} / "
                        f"{self.labels['total_layers'].get_text()}"
                    )
            if 'total_duration' in data["print_stats"]:
                self.labels["duration"].set_label(self.format_time(data["print_stats"]["total_duration"]))
            if self.state in ["printing", "paused"]:
                self.update_time_left()

        self.update_temperature_cards()

    def update_flow(self):
        if not self.flowstore:
            self.flowstore.append(0)
        self.flowrate = median(self.flowstore)
        self.flowstore = []
        self.labels['flowrate'].set_label(f"{self.flowrate:.1f} {self.mms3}")
        if 'extrusion' in self.buttons:
            self.buttons['extrusion'].set_label(f"{self.extrusion:3}% {self.flowrate:5.1f} {self.mms3}")
        return True

    def update_time_left(self):
        if "gcode_start_byte" in self.file_metadata and "gcode_end_byte" in self.file_metadata:
            byte_span = self.file_metadata["gcode_end_byte"] - self.file_metadata["gcode_start_byte"]
            if byte_span > 0:
                current = max(
                    self._printer.get_stat('virtual_sdcard', 'file_position') - self.file_metadata['gcode_start_byte'],
                    0
                )
                progress = current / byte_span
            else:
                progress = float(self._printer.get_stat('virtual_sdcard', 'progress') or 0)
        else:
            progress = float(self._printer.get_stat('virtual_sdcard', 'progress') or 0)

        last_time = self.file_metadata['last_time'] if "last_time" in self.file_metadata else 0
        slicer_time = self.file_metadata['estimated_time'] if 'estimated_time' in self.file_metadata else 0
        print_duration = float(self._printer.get_stat('print_stats', 'print_duration') or 0)
        if print_duration < 1:  # No-extrusion
            if last_time:
                print_duration = last_time * progress
            elif slicer_time:
                print_duration = slicer_time * progress
            else:
                print_duration = float(self._printer.get_stat('print_stats', 'total_duration') or 0)

        fila_used = float(self._printer.get_stat('print_stats', 'filament_used'))
        if 'filament_total' in self.file_metadata and self.file_metadata['filament_total'] >= fila_used > 0:
            filament_time = (print_duration / (fila_used / self.file_metadata['filament_total']))
            self.labels["filament_time"].set_label(self.format_time(filament_time))
        else:
            filament_time = 0
        if progress > 0:
            file_time = (print_duration / progress)
            self.labels["file_time"].set_label(self.format_time(file_time))
        else:
            file_time = 0

        estimated = 0
        timeleft_type = self._config.get_config()['main'].get('print_estimate_method', 'auto')
        if timeleft_type == "file":
            estimated = file_time
        elif timeleft_type == "filament":
            estimated = filament_time
        elif timeleft_type == "slicer":
            estimated = slicer_time
        else:
            estimated = self.estimate_time(
                progress, print_duration, file_time, filament_time, slicer_time, last_time
            )
        if estimated > 1:
            progress = min(max(print_duration / estimated, 0), 1)
            self.labels["est_time"].set_label(self.format_time(estimated))
            self.labels["time_left"].set_label(self.format_eta(estimated, print_duration))
            remaining_seconds = max(estimated - print_duration, 0)
            self.labels["remaining_time"].set_label(self.format_compact_time(remaining_seconds))
        else:
            self.labels["remaining_time"].set_label("-")

        layer_text = self.labels["layer"].get_text()
        if layer_text and "/" in layer_text and not layer_text.startswith("-"):
            self.labels["progress_detail"].set_label(layer_text.replace(" ", ""))
        else:
            file_position = int(self._printer.get_stat('virtual_sdcard', 'file_position') or 0)
            total_bytes = int(self.file_metadata.get("size") or 0)
            if total_bytes > 0:
                self.labels["progress_detail"].set_label(f"{file_position // 1024}/{total_bytes // 1024} KB")
            else:
                self.labels["progress_detail"].set_label("-")

        self.update_progress(progress)

    def estimate_time(self, progress, print_duration, file_time, filament_time, slicer_time, last_time):
        estimate_above = 0.3
        slicer_time /= sqrt(self.speed_factor)
        if progress <= estimate_above:
            return last_time or slicer_time or filament_time or file_time
        objects = self._printer.get_stat("exclude_object", "objects")
        excluded_objects = self._printer.get_stat("exclude_object", "excluded_objects")
        exclude_compensation = 3 * (len(excluded_objects) / len(objects)) if len(objects) > 0 else 0
        weight_last = 4.0 - exclude_compensation if print_duration < last_time else 0
        weight_slicer = 1.0 + estimate_above - progress - exclude_compensation if print_duration < slicer_time else 0
        weight_filament = min(progress - estimate_above, 0.33) if print_duration < filament_time else 0
        weight_file = progress - estimate_above
        total_weight = weight_last + weight_slicer + weight_filament + weight_file
        if total_weight == 0:
            return 0
        return (
            (
                last_time * weight_last
                + slicer_time * weight_slicer
                + filament_time * weight_filament
                + file_time * weight_file
            )
            / total_weight
        )

    def update_progress(self, progress: float):
        self.progress = progress
        self.labels['progress_text'].set_label(f"{trunc(progress * 100)}%")
        self.labels['darea'].queue_draw()

    def set_state(self, state, msg=""):
        if state == "printing":
            self._screen.set_panel_title(
                _("Printing") if self._printer.extrudercount > 0 else _("Working")
            )
        elif state == "complete":
            self.update_progress(1)
            self._screen.set_panel_title(_("Complete"))
            self.labels["remaining_time"].set_label("-")
            self._add_timeout(self._config.get_main_config().getint("job_complete_timeout", 0))
        elif state == "error":
            self._screen.set_panel_title(_("Error"))
            self._screen.show_popup_message(msg)
            self._add_timeout(self._config.get_main_config().getint("job_error_timeout", 0))
        elif state == "cancelling":
            self._screen.set_panel_title(_("Cancelling"))
        elif state == "cancelled" or (state == "standby" and self.state == "cancelled"):
            self._screen.set_panel_title(_("Cancelled"))
            self._add_timeout(self._config.get_main_config().getint("job_cancelled_timeout", 0))
        elif state == "paused":
            self._screen.set_panel_title(_("Paused"))
        elif state == "standby":
            self._screen.set_panel_title(_("Standby"))
        if self.state != state:
            logging.debug(f"Changing job_status state from '{self.state}' to '{state}'")
            self.state = state
            if self.thumb_dialog:
                self.close_dialog(self.thumb_dialog)
        self.show_buttons_for_state()
        self.update_temperature_cards()

    def _add_timeout(self, timeout):
        self._screen.screensaver.close()
        if timeout != 0:
            GLib.timeout_add_seconds(timeout, self.close_panel)

    def show_buttons_for_state(self):
        button_box = self.buttons['button_box']
        for child in button_box.get_children():
            button_box.remove(child)

        if self.state == "printing":
            button_box.pack_start(self.buttons['pause'], False, False, 0)
            button_box.pack_start(self.buttons['cancel'], False, False, 0)
            self.enable_button("pause", "cancel")
            self.can_close = False
        elif self.state == "paused":
            button_box.pack_start(self.buttons['resume'], False, False, 0)
            button_box.pack_start(self.buttons['cancel'], False, False, 0)
            self.enable_button("resume", "cancel")
            self.can_close = False
        else:
            if self.filename:
                button_box.pack_start(self.buttons['restart'], False, False, 0)
                self.enable_button("restart")
            else:
                self.disable_button("restart")
            if self.state != "cancelling":
                button_box.pack_start(self.buttons['menu'], False, False, 0)
                self.can_close = True
            else:
                self.can_close = False
        button_box.show_all()
        self.content.show_all()

    def show_file_thumbnail(self):
        width = self.labels['thumbnail'].get_allocated_width()
        height = self.labels['thumbnail'].get_allocated_height()
        if width <= 1 or height <= 1:
            if self._screen.vertical_mode:
                width = int(self._screen.width * 0.9)
                height = int(self._screen.height * 0.42)
            elif self.compact_mode:
                width = int(self._screen.width * 0.42)
                height = int(self._screen.height * 0.44)
            else:
                width = int(self._screen.width * 0.48)
                height = int(self._screen.height * 0.5)
        pixbuf = self.get_file_image(self.filename, width, height)
        if pixbuf is None:
            logging.debug("no pixbuf")
            return
        if image := find_widget(self.labels['thumbnail'], Gtk.Image):
            image.set_from_pixbuf(pixbuf)

    def show_fullscreen_thumbnail(self, widget):
        pixbuf = self.get_file_image(self.filename, self._screen.width * .9, self._screen.height * .75)
        if pixbuf is None:
            return
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        image.set_vexpand(True)
        self.thumb_dialog = self._gtk.Dialog(self.filename, None, image, self.close_dialog)

    def close_dialog(self, dialog=None, response_id=None):
        self._gtk.remove_dialog(dialog)
        self.thumb_dialog = None

    def update_filename(self, filename):
        if not filename or filename == self.filename:
            return

        self.filename = filename
        logging.debug(f"Updating filename to {filename}")
        self.labels["file"].set_label(os.path.splitext(self.filename)[0])
        self.labels["author"].set_label(_("Author Name"))
        self.filename_label = {
            "complete": self.labels['file'].get_label(),
            "current": self.labels['file'].get_label(),
        }
        self.get_file_metadata()

    def animate_label(self):
        if ellipsized := self.labels['file'].get_layout().is_ellipsized():
            self.filename_label['current'] = self.filename_label['current'][1:]
            self.labels['file'].set_label(self.filename_label['current'] + " " * 6)
        else:
            self.filename_label['current'] = self.filename_label['complete']
            self.labels['file'].set_label(self.filename_label['complete'])
        return True

    def get_file_metadata(self, response=False):
        if self._files.file_metadata_exists(self.filename):
            self._update_file_metadata()
        elif not response:
            logging.debug("Cannot find file metadata. Listening for updated metadata")
            self._files.request_metadata(self.filename)
        else:
            logging.debug("Cannot load file metadata")
        self.show_file_thumbnail()

    def _update_file_metadata(self):
        self.file_metadata = self._files.get_file_info(self.filename)
        logging.info(f"Update Metadata. File: {self.filename} Size: {self.file_metadata['size']}")
        if "estimated_time" in self.file_metadata:
            if self.timeleft_type == "slicer":
                self.labels["est_time"].set_label(self.format_time(self.file_metadata['estimated_time']))
            self.labels["slicer_time"].set_label(self.format_time(self.file_metadata['estimated_time']))
        if "object_height" in self.file_metadata:
            self.oheight = float(self.file_metadata['object_height'])
            self.labels['height'].set_label(f"{self.oheight:.2f} {self.mm}")
        if "filament_total" in self.file_metadata:
            self.labels['filament_total'].set_label(f"{float(self.file_metadata['filament_total']) / 1000:.1f} m")
        if "job_id" in self.file_metadata and self.file_metadata['job_id']:
            history = self._screen.apiclient.send_request(f"server/history/job?uid={self.file_metadata['job_id']}")
            if history and history['job']['status'] == "completed" and history['job']['print_duration']:
                self.file_metadata["last_time"] = history['job']['print_duration']

        author = (
            self.file_metadata.get("author")
            or self.file_metadata.get("modified_by")
            or self.file_metadata.get("slicer")
            or _("Author Name")
        )
        self.labels["author"].set_label(str(author))
