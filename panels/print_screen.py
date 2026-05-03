import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.content.get_style_context().add_class("customBG")

        # Main centered layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_hexpand(True)
        main_box.set_vexpand(True)
        main_box.set_halign(Gtk.Align.CENTER)
        main_box.set_valign(Gtk.Align.CENTER)
        self.content.add(main_box)
 
        # Print Queue section
        queue_title = Gtk.Label(label="Print Queue")
        queue_title.get_style_context().add_class("queue-button")
        main_box.pack_start(queue_title, False, False, 0)

        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        toggle_box.set_halign(Gtk.Align.CENTER)

        self.enable_btn = Gtk.Button(label="Enable")
        self.enable_btn.get_style_context().add_class("jog-distance")
        self.enable_btn.connect("clicked", self._on_queue_toggle, True)

        self.disable_btn = Gtk.Button(label="Disable")
        self.disable_btn.get_style_context().add_class("jog-distance")
        self.disable_btn.get_style_context().add_class("jog-distance-active")
        self.disable_btn.connect("clicked", self._on_queue_toggle, False)

        toggle_box.pack_start(self.enable_btn, False, False, 0)
        toggle_box.pack_start(self.disable_btn, False, False, 0)
        main_box.pack_start(toggle_box, False, False, 0)

        # Manual Print button
        manual_btn = Gtk.Button()
        manual_btn.get_style_context().add_class("queue-button")
        manual_lbl = Gtk.Label(label="Manual Print")
        manual_btn.add(manual_lbl)
        manual_btn.connect("clicked", self._manual_print)
        main_box.pack_start(manual_btn, False, False, 0)

    def _on_queue_toggle(self, widget, enabled):
        if enabled:
            self.enable_btn.get_style_context().add_class("jog-distance-active")
            self.disable_btn.get_style_context().remove_class("jog-distance-active")
            script = 'SET_DISPLAY_TEXT MSG="Ready"'
        else:
            self.disable_btn.get_style_context().add_class("jog-distance-active")
            self.enable_btn.get_style_context().remove_class("jog-distance-active")
            script = 'SET_DISPLAY_TEXT MSG="Nope"'
        self._screen._send_action(widget, "printer.gcode.script", {"script": script})

    def _manual_print(self, widget):
        """Open the file browser for manual print selection."""
        self._screen.show_panel("gcodes")
