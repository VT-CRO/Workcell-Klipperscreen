import logging
import os
import pathlib

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf
from ks_includes.screen_panel import ScreenPanel


# Filament temperature profiles: (nozzle_temp, bed_temp)
FILAMENT_PROFILES = {
    'PLA':  (210, 60),
    'PETG': (230, 80),
    'ABS':  (240, 100),
    'N/A':  (0, 0),
}

# Spool colors for display: (fill_r, fill_g, fill_b) for the spool icon tint
SPOOL_COLORS = {
    'PLA':  (0.93, 0.16, 0.16),   # Red
    'PETG': (0.88, 0.88, 0.88),   # White/gray
    'ABS':  (0.30, 0.30, 0.30),   # Dark gray
    'N/A':  (0.30, 0.30, 0.30),   # Dark gray
}


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.content.get_style_context().add_class("customBG")

        styles_dir = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles")
        self.spool_svg_path = os.path.join(styles_dir, "spool.svg")
        self.pencil_svg_path = os.path.join(styles_dir, "pencil.svg")

        self.selected_filament = None
        self.filament_buttons = {}   # slot_idx → Gtk.Button
        self.slot_lane_names = {}    # slot_idx → AFC lane name (e.g. "lane1")
        self.slot_materials = {}     # slot_idx → material string (e.g. "PLA") or ""
        self.slot_has_filament = {}  # slot_idx → bool
        self.slot_icon_stacks = {}   # slot_idx → Gtk.Stack (spool / pencil pages)

        # Check if UNLOAD_FILAMENT macro exists
        macros = self._printer.get_config_section_list("gcode_macro ")
        self.has_unload = any("UNLOAD_FILAMENT" in macro.upper() for macro in macros)

        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_hexpand(True)
        main_box.set_vexpand(True)
        main_box.set_margin_top(20)
        main_box.set_margin_start(30)
        main_box.set_margin_end(30)
        main_box.set_margin_bottom(12)
        self.content.add(main_box)

        # 2x2 grid of filament buttons
        grid = Gtk.Grid()
        grid.set_row_spacing(12)
        grid.set_column_spacing(12)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_valign(Gtk.Align.CENTER)
        grid.set_vexpand(True)
        grid.set_hexpand(True)
        grid.set_row_homogeneous(True)
        grid.set_column_homogeneous(True)

        afc_slots = self._fetch_afc_slots()  # [(lane_name, material), ...] up to 4
        positions = [(0, 0), (1, 0), (0, 1), (1, 1)]

        for slot_idx, (col, row) in enumerate(positions):
            lane_name, material, has_filament = afc_slots[slot_idx] if slot_idx < len(afc_slots) else (None, "", False)
            self.slot_lane_names[slot_idx] = lane_name
            self.slot_materials[slot_idx] = material
            self.slot_has_filament[slot_idx] = has_filament
            btn = self._create_filament_button(slot_idx, lane_name, material, has_filament)
            self.filament_buttons[slot_idx] = btn
            grid.attach(btn, col, row, 1, 1)

        main_box.pack_start(grid, True, True, 0)

        # Unload Filament button
        unload_btn = Gtk.Button()
        unload_btn.get_style_context().add_class("filament-unload")
        unload_lbl = Gtk.Label(label="Unload Filament")
        unload_btn.add(unload_lbl)
        unload_btn.set_hexpand(True)
        unload_btn.connect("clicked", self._unload_filament)
        if not self.has_unload:
            unload_btn.set_sensitive(False)
        main_box.pack_end(unload_btn, False, False, 0)

    def _fetch_afc_slots(self):
        """Query AFC status and return [(lane_name, material), ...] sorted by lane number."""
        try:
            result = self._screen.apiclient.post_request("printer/afc/status", json={})
            afc_data = result.get('result', {}).get('status:', {}).get('AFC', {})
            lanes = []
            for _, unit_data in sorted(afc_data.items()):
                if not isinstance(unit_data, dict):
                    continue
                for lane_name, lane_data in sorted(unit_data.items()):
                    if not isinstance(lane_data, dict) or not lane_name.startswith("lane"):
                        continue
                    material = (lane_data.get("material") or "").strip().upper()
                    has_filament = bool(lane_data.get("load") or lane_data.get("prep"))
                    lanes.append((lane_name, material, has_filament))
            return lanes[:4]
        except Exception as e:
            logging.warning(f"Could not fetch AFC status: {e}")
            return []

    def _create_filament_button(self, slot_idx, lane_name, material, has_filament=False):
        """Create a filament slot button showing the AFC lane material."""
        btn = Gtk.Button()
        btn.get_style_context().add_class("filament-button")
        btn.set_hexpand(True)
        btn.set_vexpand(True)

        inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        inner.set_halign(Gtk.Align.CENTER)
        inner.set_valign(Gtk.Align.CENTER)

        # Icon area: stack that shows spool normally, pencil when selected
        icon_stack = Gtk.Stack()
        icon_stack.set_transition_type(Gtk.StackTransitionType.NONE)
        icon_stack.set_size_request(48, 48)

        spool_area = Gtk.DrawingArea()
        spool_area.set_size_request(48, 48)
        r, g, b = SPOOL_COLORS.get(material, (0.5, 0.5, 0.5))
        spool_area.connect("draw", self._draw_spool, r, g, b)
        icon_stack.add_named(spool_area, "spool")

        pencil_btn = Gtk.Button()
        pencil_btn.get_style_context().add_class("filament-pencil")
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(self.pencil_svg_path, 32, 32)
            pencil_img = Gtk.Image.new_from_pixbuf(pixbuf)
        except Exception:
            pencil_img = Gtk.Image.new_from_icon_name("document-edit", Gtk.IconSize.LARGE_TOOLBAR)
        pencil_btn.add(pencil_img)
        pencil_btn.set_size_request(48, 48)
        pencil_btn.connect("clicked", lambda *_: None)  # placeholder
        icon_stack.add_named(pencil_btn, "pencil")

        icon_stack.set_visible_child_name("spool")
        self.slot_icon_stacks[slot_idx] = icon_stack
        inner.pack_start(icon_stack, False, False, 0)

        # Label: material if known, "N/A" if loaded but unknown, "Empty" if no filament
        display = material if material else ("N/A" if has_filament else "Empty")
        lbl = Gtk.Label(label=display)
        lbl.set_halign(Gtk.Align.START)
        inner.pack_start(lbl, False, False, 0)

        btn.add(inner)
        btn.connect("clicked", self._select_filament, slot_idx)

        return btn

    def _draw_spool(self, widget, ctx, r, g, b):
        """Draw a simple spool icon."""
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        cx = w / 2
        cy = h / 2
        radius = min(w, h) / 2 - 2

        # Outer ring
        ctx.set_source_rgb(r, g, b)
        ctx.arc(cx, cy, radius, 0, 2 * 3.14159)
        ctx.fill()

        # Inner hole (dark)
        ctx.set_source_rgb(0.12, 0.13, 0.16)
        ctx.arc(cx, cy, radius * 0.35, 0, 2 * 3.14159)
        ctx.fill()

        # Rim highlight
        ctx.set_source_rgba(1, 1, 1, 0.15)
        ctx.set_line_width(2)
        ctx.arc(cx, cy, radius - 1, 0, 2 * 3.14159)
        ctx.stroke()

        return True

    def _select_filament(self, widget, slot_idx):
        """Select a filament slot and set temperature profile."""
        # Reset all buttons and icon stacks
        for idx, btn in self.filament_buttons.items():
            btn.get_style_context().remove_class("filament-selected")
            stack = self.slot_icon_stacks.get(idx)
            if stack:
                stack.set_visible_child_name("spool")

        widget.get_style_context().add_class("filament-selected")
        self.selected_filament = slot_idx

        # Show pencil only for non-empty slots
        if self.slot_materials.get(slot_idx) or self.slot_has_filament.get(slot_idx):
            stack = self.slot_icon_stacks.get(slot_idx)
            if stack:
                stack.set_visible_child_name("pencil")

        filament_type = self.slot_materials.get(slot_idx, "")

        # Set temperature profile
        nozzle_temp, bed_temp = FILAMENT_PROFILES.get(filament_type, (0, 0))
        if nozzle_temp > 0:
            self._screen._ws.klippy.set_tool_temp(
                self._printer.get_tool_number("extruder"), nozzle_temp
            )
            logging.info(f"Set nozzle temp to {nozzle_temp}°C for {filament_type}")
        if bed_temp > 0:
            self._screen._ws.klippy.set_bed_temp(bed_temp)
            logging.info(f"Set bed temp to {bed_temp}°C for {filament_type}")

    def _unload_filament(self, widget):
        """Run the UNLOAD_FILAMENT macro."""
        if self.has_unload:
            self._screen._send_action(
                widget, "printer.gcode.script",
                {"script": "UNLOAD_FILAMENT"}
            )
            logging.info("Unload filament command sent")
        else:
            self._screen.show_popup_message("UNLOAD_FILAMENT macro not found")

    # --- AFC integration ---

    def afc_change_tool(self, lane_name):
        """Switch the active tool to the given AFC lane. (CHANGE_TOOL LANE=<name>)"""
        self._screen._ws.klippy.gcode_script(f"CHANGE_TOOL LANE={lane_name}")
        logging.info(f"AFC: CHANGE_TOOL LANE={lane_name}")

    def afc_lane_unload(self, lane_name):
        """Eject filament from a specific AFC lane. (LANE_UNLOAD LANE=<name>)"""
        self._screen._ws.klippy.gcode_script(f"LANE_UNLOAD LANE={lane_name}")
        logging.info(f"AFC: LANE_UNLOAD LANE={lane_name}")

    def afc_tool_unload(self):
        """Retract filament from the extruder back to the AFC. (TOOL_UNLOAD)"""
        self._screen._ws.klippy.gcode_script("TOOL_UNLOAD")
        logging.info("AFC: TOOL_UNLOAD")

    def afc_set_lane_loaded(self, lane_name):
        """Mark a lane as the currently loaded lane. (SET_LANE_LOADED LANE=<name>)"""
        self._screen._ws.klippy.gcode_script(f"SET_LANE_LOADED LANE={lane_name}")
        logging.info(f"AFC: SET_LANE_LOADED LANE={lane_name}")

    def afc_unset_lane_loaded(self):
        """Clear the currently loaded lane marker. (UNSET_LANE_LOADED)"""
        self._screen._ws.klippy.gcode_script("UNSET_LANE_LOADED")
        logging.info("AFC: UNSET_LANE_LOADED")

    def afc_get_status(self, callback):
        """Query AFC filament status for all lanes.

        callback(result) is called with the raw AFC status dict:
            result['result']['status']['AFC']
        """
        self._screen.apiclient.send_request(
            "printer/afc/status",
            callback,
        )
