import logging
import os
import pathlib

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, Gtk

from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    selected_material = "pla"

    def __init__(self, screen, title):
        title = title or _("Filament")
        super().__init__(screen, title)

        self.content.get_style_context().add_class("workcell-bg")
        self.compact_mode = not self._screen.vertical_mode and self._screen.width <= 800 and self._screen.height <= 480

        styles_dir = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles")
        self.paths = {
            "mark": os.path.join(styles_dir, "workcell-mark.svg"),
            "home": os.path.join(styles_dir, "home.svg"),
            "home_active": os.path.join(styles_dir, "home-dark.svg"),
            "settings": os.path.join(styles_dir, "sliders.svg"),
            "settings_active": os.path.join(styles_dir, "sliders-dark.svg"),
            "files": os.path.join(styles_dir, "menu-bars.svg"),
            "files_active": os.path.join(styles_dir, "menu-bars-dark.svg"),
            "spool_nav": os.path.join(styles_dir, "spool-nav.svg"),
            "spool_nav_active": os.path.join(styles_dir, "spool-nav-dark.svg"),
            "spool_asset": os.path.join(styles_dir, "spool.svg"),
        }
        self.spool_svg = pathlib.Path(self.paths["spool_asset"]).read_text()
        self.current_extruder = self._printer.get_stat("toolhead", "extruder") or "extruder"

        self.material_buttons = {}
        self.material_profiles = {
            "pla": {"label": "PLA", "color": "FF3A3A", "nozzle": 210, "bed": 60, "enabled": True},
            "petg": {"label": "PETG", "color": "FFFFFF", "nozzle": 240, "bed": 80, "enabled": True},
            "abs": {"label": "ABS", "color": "101010", "nozzle": 250, "bed": 100, "enabled": True},
            "na": {"label": "N/A", "color": "4A4F56", "nozzle": None, "bed": None, "enabled": False},
        }

        root_orientation = Gtk.Orientation.VERTICAL if self._screen.vertical_mode else Gtk.Orientation.HORIZONTAL
        self.root = Gtk.Box(orientation=root_orientation, spacing=0)
        self.root.get_style_context().add_class("workcell-root")
        if self.compact_mode:
            self.root.get_style_context().add_class("workcell-compact")
        self.content.add(self.root)

        self.sidebar = self.create_sidebar()
        self.root.pack_start(self.sidebar, False, False, 0)

        self.main_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12 if self.compact_mode else 18)
        self.main_area.get_style_context().add_class("workcell-main-area")
        if self._screen.vertical_mode:
            self.main_area.set_margin_top(14)
            self.main_area.set_margin_start(14)
            self.main_area.set_margin_end(14)
            self.main_area.set_margin_bottom(14)
        elif self.compact_mode:
            self.main_area.set_margin_top(8)
            self.main_area.set_margin_start(10)
            self.main_area.set_margin_end(10)
            self.main_area.set_margin_bottom(8)
        else:
            self.main_area.set_margin_top(20)
            self.main_area.set_margin_start(22)
            self.main_area.set_margin_end(22)
            self.main_area.set_margin_bottom(20)
        self.root.pack_start(self.main_area, True, True, 0)

        self.main_area.pack_start(self._build_filament_grid(), True, True, 0)

        unload_btn = Gtk.Button(label=_("Unload Filament"))
        unload_btn.get_style_context().add_class("workcell-queue-button")
        unload_btn.connect("clicked", self.unload_filament)
        self.main_area.pack_end(unload_btn, False, False, 0)

        self.refresh_selection()

    def _image_from_file(self, path, width, height):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, width, height)
            return Gtk.Image.new_from_pixbuf(pixbuf)
        except Exception as err:
            logging.debug(f"Unable to load image {path}: {err}")
            return Gtk.Image()

    def _spool_image(self, color_hex, width, height):
        try:
            loader = GdkPixbuf.PixbufLoader()
            loader.write(self.spool_svg.replace("var(--filament-color)", f"#{color_hex}").encode())
            loader.close()
            pixbuf = loader.get_pixbuf()
            if pixbuf is not None:
                pixbuf = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
                return Gtk.Image.new_from_pixbuf(pixbuf)
        except Exception as err:
            logging.debug(f"Unable to render spool icon ({color_hex}): {err}")
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
            self._nav_button(self.paths["settings"], button_size, icon_size, self.go_controls), False, False, 0
        )
        sidebar.pack_start(
            self._nav_button(self.paths["files"], button_size, icon_size, self.go_queue), False, False, 0
        )
        sidebar.pack_start(
            self._nav_button(self.paths["spool_nav_active"], button_size, icon_size, self.go_filament, is_active=True),
            False,
            False,
            0,
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

    def _build_filament_grid(self):
        grid = Gtk.Grid(column_spacing=12 if self.compact_mode else 16, row_spacing=12 if self.compact_mode else 16)
        grid.set_halign(Gtk.Align.FILL)
        grid.set_valign(Gtk.Align.CENTER)
        grid.set_hexpand(True)
        grid.set_vexpand(True)

        order = [("pla", 0, 0), ("petg", 1, 0), ("abs", 0, 1), ("na", 1, 1)]
        for key, col, row in order:
            cfg = self.material_profiles[key]
            button = Gtk.Button()
            button.get_style_context().add_class("workcell-filament-button")
            button.set_hexpand(True)
            button.set_vexpand(True)
            button.set_sensitive(cfg["enabled"])

            body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10 if self.compact_mode else 14)
            body.set_margin_start(14 if self.compact_mode else 18)
            body.set_margin_end(14 if self.compact_mode else 18)
            body.set_margin_top(12 if self.compact_mode else 16)
            body.set_margin_bottom(12 if self.compact_mode else 16)

            spool_icon = self._spool_image(cfg["color"], 44 if self.compact_mode else 58, 44 if self.compact_mode else 58)
            body.pack_start(spool_icon, False, False, 0)

            label = Gtk.Label(label=cfg["label"], xalign=0)
            label.get_style_context().add_class("workcell-filament-label")
            body.pack_start(label, True, True, 0)
            button.add(body)

            button.connect("clicked", self.select_material, key)
            grid.attach(button, col, row, 1, 1)
            self.material_buttons[key] = button

        return grid

    def refresh_selection(self):
        for key, button in self.material_buttons.items():
            ctx = button.get_style_context()
            if key == self.selected_material:
                ctx.add_class("workcell-filament-button-active")
            else:
                ctx.remove_class("workcell-filament-button-active")

    def select_material(self, widget, material_key):
        cfg = self.material_profiles.get(material_key)
        if cfg is None or not cfg["enabled"]:
            return

        Panel.selected_material = material_key
        self.refresh_selection()

        nozzle = cfg["nozzle"]
        bed = cfg["bed"]
        if nozzle is not None and self.current_extruder:
            self._screen._ws.klippy.set_tool_temp(self._printer.get_tool_number(self.current_extruder), nozzle)
        if bed is not None:
            self._screen._ws.klippy.set_bed_temp(bed)
        self._screen.show_popup_message(
            _("Applied {name} profile").format(name=cfg["label"]) + f" ({nozzle}°/{bed}°)",
            level=1,
        )

    def unload_filament(self, widget):
        self._screen._send_action(widget, "printer.gcode.script", {"script": "UNLOAD_FILAMENT"})
        self._screen.show_popup_message(_("Unload filament routine started"), level=1)

    def _safe_show_panel(self, panel_name):
        try:
            self._screen.show_panel(panel_name)
        except Exception as err:
            logging.debug(f"Unable to open panel '{panel_name}': {err}")
            self._screen.show_popup_message(_("Panel is not available"))

    def go_home(self, widget):
        self._screen._menu_go_back(home=True)

    def go_controls(self, widget):
        self._safe_show_panel("move")

    def go_queue(self, widget):
        self._safe_show_panel("print_screen")

    def go_filament(self, widget):
        return

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        current_extruder = self._printer.get_stat("toolhead", "extruder")
        if current_extruder:
            self.current_extruder = current_extruder
