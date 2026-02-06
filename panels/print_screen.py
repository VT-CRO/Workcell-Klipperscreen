import logging
import os
import pathlib

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, Gtk

from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Queue")
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
            "spool": os.path.join(styles_dir, "spool-nav.svg"),
            "spool_active": os.path.join(styles_dir, "spool-nav-dark.svg"),
        }

        root_orientation = Gtk.Orientation.VERTICAL if self._screen.vertical_mode else Gtk.Orientation.HORIZONTAL
        self.root = Gtk.Box(orientation=root_orientation, spacing=0)
        self.root.get_style_context().add_class("workcell-root")
        if self.compact_mode:
            self.root.get_style_context().add_class("workcell-compact")
        self.content.add(self.root)

        self.sidebar = self.create_sidebar()
        self.root.pack_start(self.sidebar, False, False, 0)

        self.main_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16 if self.compact_mode else 24)
        self.main_area.get_style_context().add_class("workcell-main-area")
        if self._screen.vertical_mode:
            self.main_area.set_margin_top(16)
            self.main_area.set_margin_start(16)
            self.main_area.set_margin_end(16)
            self.main_area.set_margin_bottom(16)
        elif self.compact_mode:
            self.main_area.set_margin_top(20)
            self.main_area.set_margin_start(18)
            self.main_area.set_margin_end(18)
            self.main_area.set_margin_bottom(20)
        else:
            self.main_area.set_margin_top(28)
            self.main_area.set_margin_start(28)
            self.main_area.set_margin_end(28)
            self.main_area.set_margin_bottom(28)
        self.root.pack_start(self.main_area, True, True, 0)

        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16 if self.compact_mode else 22)
        center.set_halign(Gtk.Align.CENTER)
        center.set_valign(Gtk.Align.CENTER)
        center.set_hexpand(True)
        center.set_vexpand(True)

        queue_start = Gtk.Button(label=_("Queue Start"))
        queue_start.get_style_context().add_class("workcell-queue-button")
        queue_start.connect("clicked", self.start_queue)

        manual_print = Gtk.Button(label=_("Manual Print"))
        manual_print.get_style_context().add_class("workcell-queue-button")
        manual_print.connect("clicked", self.open_manual_print)

        center.pack_start(queue_start, False, False, 0)
        center.pack_start(manual_print, False, False, 0)
        self.main_area.pack_start(center, True, True, 0)

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
            self._nav_button(self.paths["settings"], button_size, icon_size, self.go_controls), False, False, 0
        )
        sidebar.pack_start(
            self._nav_button(self.paths["files_active"], button_size, icon_size, self.go_queue, is_active=True),
            False,
            False,
            0,
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
        return

    def go_filament(self, widget):
        self._safe_show_panel("filament")

    def start_queue(self, widget):
        self._screen._send_action(widget, "printer.gcode.script", {"script": "START_QUEUE"})
        self._screen.show_popup_message(_("Queue start command sent"), level=1)

    def open_manual_print(self, widget):
        self._safe_show_panel("gcodes")
