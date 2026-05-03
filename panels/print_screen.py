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

        switch_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        switch_box.set_halign(Gtk.Align.CENTER)

        enable_lbl = Gtk.Label(label="Enable")
        self.queue_switch = Gtk.Switch()
        self.queue_switch.set_active(False)
        self.queue_switch.connect("notify::active", self._on_queue_switch)
        disable_lbl = Gtk.Label(label="Disable")

        switch_box.pack_start(enable_lbl, False, False, 0)
        switch_box.pack_start(self.queue_switch, False, False, 0)
        switch_box.pack_start(disable_lbl, False, False, 0)
        main_box.pack_start(switch_box, False, False, 0)

        # Manual Print button
        manual_btn = Gtk.Button()
        manual_btn.get_style_context().add_class("queue-button")
        manual_lbl = Gtk.Label(label="Manual Print")
        manual_btn.add(manual_lbl)
        manual_btn.connect("clicked", self._manual_print)
        main_box.pack_start(manual_btn, False, False, 0)

    def _on_queue_switch(self, switch, _param):
        if switch.get_active():
            script = 'SET_DISPLAY_TEXT MSG="Ready"'
        else:
            script = 'SET_DISPLAY_TEXT MSG="Nope"'
        self._screen._send_action(switch, "printer.gcode.script", {"script": script})

    def _manual_print(self, widget):
        """Open the file browser for manual print selection."""
        self._screen.show_panel("gcodes")
