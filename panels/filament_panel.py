import logging
import os
import pathlib

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf
from ks_includes.screen_panel import ScreenPanel


# Filament temperature profiles: (nozzle_temp, bed_temp)
FILAMENT_PROFILES = {
    'PLA':  (210, 60),
    'PETG': (230, 80),
    'ABS':  (240, 100),
}

# Spool colors for display: (fill_r, fill_g, fill_b)
SPOOL_COLORS = {
    'PLA':  (0.93, 0.16, 0.16),
    'PETG': (0.88, 0.88, 0.88),
    'ABS':  (0.30, 0.30, 0.30),
}

FILAMENT_OPTIONS = ['PLA', 'PETG', 'ABS']


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.content.get_style_context().add_class("customBG")

        styles_dir = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles")
        self.spool_svg_path = os.path.join(styles_dir, "spool.svg")
        self.pencil_svg_path = os.path.join(styles_dir, "pencil.svg")

        self.selected_filament = None
        self.filament_buttons = {}      # slot_idx → Gtk.Button
        self.slot_lane_names = {}       # slot_idx → AFC lane name (e.g. "lane1")
        self.slot_materials = {}        # slot_idx → material string (e.g. "PLA") or ""
        self.slot_has_filament = {}     # slot_idx → bool
        self.slot_icon_stacks = {}      # slot_idx → Gtk.Stack (spool / pencil pages)
        self.slot_material_labels = {}  # slot_idx → Gtk.Label for the material text
        self.slot_spool_areas = {}      # slot_idx → Gtk.DrawingArea
        self.slot_spool_colors = {}     # slot_idx → [r, g, b] mutable for live updates
        self._edit_popup_widget = None   # current overlay blocker, or None
        self._edit_selected_type = None  # mutable [type] list used by the open popup

        # Check if UNLOAD_FILAMENT macro exists
        macros = self._printer.get_config_section_list("gcode_macro ")
        self.has_unload = any("UNLOAD_FILAMENT" in macro.upper() for macro in macros)

        # Main layout wrapped in Overlay so the edit popup can float on top
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_hexpand(True)
        main_box.set_vexpand(True)
        main_box.set_margin_top(20)
        main_box.set_margin_start(30)
        main_box.set_margin_end(30)
        main_box.set_margin_bottom(12)

        self._overlay = Gtk.Overlay()
        self._overlay.add(main_box)
        self.content.add(self._overlay)

        # Single row of 4 lane buttons
        geo = Gdk.Display.get_default().get_primary_monitor().get_geometry()
        lane_row_w = int(geo.width * 4 / 5)

        lane_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lane_row.set_size_request(lane_row_w, -1)
        lane_row.set_halign(Gtk.Align.CENTER)
        lane_row.set_vexpand(False)
        lane_row.set_homogeneous(True)

        afc_slots = self._fetch_afc_slots()

        for slot_idx in range(4):
            lane_name, material, has_filament = (
                afc_slots[slot_idx] if slot_idx < len(afc_slots) else (None, "", False)
            )
            self.slot_lane_names[slot_idx] = lane_name
            self.slot_materials[slot_idx] = material
            self.slot_has_filament[slot_idx] = has_filament
            btn = self._create_filament_button(slot_idx, lane_name, material, has_filament)
            self.filament_buttons[slot_idx] = btn
            lane_row.pack_start(btn, True, True, 0)

        main_box.pack_start(lane_row, False, False, 0)

        # Load / Unload buttons side by side
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        action_box.set_hexpand(True)

        self._load_btn = Gtk.Button()
        self._load_btn.get_style_context().add_class("filament-unload")
        self._load_btn.add(Gtk.Label(label="Load Filament"))
        self._load_btn.set_hexpand(True)
        self._load_btn.set_sensitive(False)
        self._load_btn.connect("clicked", self._load_filament)
        action_box.pack_start(self._load_btn, True, True, 0)

        self._unload_btn = Gtk.Button()
        self._unload_btn.get_style_context().add_class("filament-unload")
        self._unload_btn.add(Gtk.Label(label="Unload Filament"))
        self._unload_btn.set_hexpand(True)
        self._unload_btn.set_sensitive(False)
        self._unload_btn.connect("clicked", self._unload_filament)
        action_box.pack_start(self._unload_btn, True, True, 0)

        main_box.pack_end(action_box, False, False, 0)

    # ------------------------------------------------------------------ #
    #  Data                                                                #
    # ------------------------------------------------------------------ #

    def _fetch_afc_slots(self):
        """Return [(lane_name, material, has_filament), ...] from AFC, up to 4."""
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

    # ------------------------------------------------------------------ #
    #  Button construction                                                 #
    # ------------------------------------------------------------------ #

    def _create_filament_button(self, slot_idx, lane_name, material, has_filament=False):
        """Create a filament slot button showing the AFC lane material."""
        btn = Gtk.Button()
        btn.get_style_context().add_class("filament-button")
        btn.set_hexpand(True)
        btn.set_vexpand(False)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner.set_halign(Gtk.Align.CENTER)
        inner.set_valign(Gtk.Align.CENTER)
        inner.set_hexpand(True)
        inner.set_vexpand(True)

        # --- Icon stack: spool (default) ↔ pencil (when selected) ---
        icon_stack = Gtk.Stack()
        icon_stack.set_transition_type(Gtk.StackTransitionType.NONE)
        icon_stack.set_size_request(56, 56)
        icon_stack.set_halign(Gtk.Align.CENTER)

        spool_area = Gtk.DrawingArea()
        spool_area.set_size_request(56, 56)
        self.slot_spool_colors[slot_idx] = list(SPOOL_COLORS.get(material, (0.5, 0.5, 0.5)))
        self.slot_spool_areas[slot_idx] = spool_area
        spool_area.connect(
            "draw",
            lambda w, ctx, si=slot_idx: self._draw_spool_slot(w, ctx, si),
        )
        icon_stack.add_named(spool_area, "spool")

        pencil_box = Gtk.Box()
        pencil_box.get_style_context().add_class("filament-pencil")
        pencil_box.set_size_request(56, 56)
        pencil_box.set_halign(Gtk.Align.CENTER)
        pencil_box.set_valign(Gtk.Align.CENTER)
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(self.pencil_svg_path, 40, 40)
            pencil_img = Gtk.Image.new_from_pixbuf(pixbuf)
        except Exception:
            pencil_img = Gtk.Image.new_from_icon_name("document-edit", Gtk.IconSize.LARGE_TOOLBAR)
        pencil_box.pack_start(pencil_img, True, True, 0)
        icon_stack.add_named(pencil_box, "pencil")

        icon_stack.set_visible_child_name("spool")
        self.slot_icon_stacks[slot_idx] = icon_stack
        inner.pack_start(icon_stack, False, False, 0)

        # --- Material label ---
        display = material if material else ("N/A" if has_filament else "Empty")
        lbl = Gtk.Label(label=display)
        lbl.set_halign(Gtk.Align.CENTER)
        self.slot_material_labels[slot_idx] = lbl
        inner.pack_start(lbl, False, False, 0)

        btn.add(inner)
        btn.connect("clicked", self._select_filament, slot_idx)
        return btn

    # ------------------------------------------------------------------ #
    #  Drawing                                                             #
    # ------------------------------------------------------------------ #

    def _draw_spool_slot(self, widget, ctx, slot_idx):
        """Draw spool icon using the current stored color for this slot."""
        r, g, b = self.slot_spool_colors.get(slot_idx, [0.5, 0.5, 0.5])
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        cx, cy = w / 2, h / 2
        radius = min(w, h) / 2 - 2

        ctx.set_source_rgb(r, g, b)
        ctx.arc(cx, cy, radius, 0, 2 * 3.14159)
        ctx.fill()

        ctx.set_source_rgb(0.12, 0.13, 0.16)
        ctx.arc(cx, cy, radius * 0.35, 0, 2 * 3.14159)
        ctx.fill()

        ctx.set_source_rgba(1, 1, 1, 0.15)
        ctx.set_line_width(2)
        ctx.arc(cx, cy, radius - 1, 0, 2 * 3.14159)
        ctx.stroke()

        return True

    # ------------------------------------------------------------------ #
    #  Edit popup                                                          #
    # ------------------------------------------------------------------ #

    def _open_edit_popup(self, slot_idx):
        """Show the filament type edit popup for the given slot."""
        if self._edit_popup_widget is not None:
            return  # already open

        # Measure screen so the popup can fill 70%
        monitor = Gdk.Display.get_default().get_primary_monitor()
        geo = monitor.get_geometry()
        popup_w = int(geo.width * 0.70)
        popup_h = int(geo.height * 0.70)

        # Full-area EventBox — absorbs all clicks so nothing behind it is reachable
        blocker = Gtk.EventBox()
        blocker.set_hexpand(True)
        blocker.set_vexpand(True)
        blocker.get_style_context().add_class("filament-edit-overlay")

        # Centered popup card
        popup = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        popup.get_style_context().add_class("filament-edit-popup")
        popup.set_halign(Gtk.Align.CENTER)
        popup.set_valign(Gtk.Align.CENTER)
        popup.set_size_request(popup_w, popup_h)

        # Header: title + X button
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        title_lbl = Gtk.Label(label="Edit Filament Type")
        title_lbl.get_style_context().add_class("filament-edit-title")
        close_btn = Gtk.Button(label="✕")
        close_btn.get_style_context().add_class("filament-edit-close")
        close_btn.connect("clicked", lambda *_: self._close_edit_popup())
        header.pack_start(title_lbl, True, True, 0)
        header.pack_end(close_btn, False, False, 0)
        popup.pack_start(header, False, False, 0)

        # Filament type toggle buttons
        current = self.slot_materials.get(slot_idx, "")
        self._edit_selected_type = [current if current in FILAMENT_OPTIONS else FILAMENT_OPTIONS[0]]
        type_btns = {}

        type_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        type_box.set_hexpand(True)

        def on_type_toggled(btn, ft):
            if btn.get_active():
                self._edit_selected_type[0] = ft
                for other_ft, other_btn in type_btns.items():
                    if other_ft != ft and other_btn.get_active():
                        other_btn.handler_block_by_func(on_type_toggled)
                        other_btn.set_active(False)
                        other_btn.handler_unblock_by_func(on_type_toggled)

        for ft in FILAMENT_OPTIONS:
            tb = Gtk.ToggleButton(label=ft)
            tb.get_style_context().add_class("filament-type-btn")
            tb.set_hexpand(True)
            tb.set_active(ft == self._edit_selected_type[0])
            type_btns[ft] = tb
            tb.connect("toggled", on_type_toggled, ft)
            type_box.pack_start(tb, True, True, 0)

        popup.pack_start(type_box, False, False, 0)

        # Confirm button
        confirm_btn = Gtk.Button(label="Confirm")
        confirm_btn.get_style_context().add_class("filament-edit-confirm")
        confirm_btn.connect("clicked", lambda *_: self._confirm_filament_edit(slot_idx))
        popup.pack_end(confirm_btn, False, False, 0)

        blocker.add(popup)
        blocker.show_all()

        self._edit_popup_widget = blocker
        self._overlay.add_overlay(blocker)
        self._overlay.set_overlay_pass_through(blocker, False)

    def _close_edit_popup(self):
        """Remove the edit popup overlay."""
        if self._edit_popup_widget is not None:
            self._overlay.remove(self._edit_popup_widget)
            self._edit_popup_widget = None
            self._edit_selected_type = None

    def _confirm_filament_edit(self, slot_idx):
        """Apply the chosen filament type to the slot, push to AFC, and close the popup."""
        new_material = self._edit_selected_type[0] if self._edit_selected_type else None
        if new_material:
            self.slot_materials[slot_idx] = new_material
            self.slot_has_filament[slot_idx] = True

            lbl = self.slot_material_labels.get(slot_idx)
            if lbl:
                lbl.set_text(new_material)

            self.slot_spool_colors[slot_idx] = list(SPOOL_COLORS.get(new_material, (0.5, 0.5, 0.5)))
            spool_area = self.slot_spool_areas.get(slot_idx)
            if spool_area:
                spool_area.queue_draw()

            # Persist to AFC so the change survives navigation
            lane_name = self.slot_lane_names.get(slot_idx)
            if lane_name:
                self._screen._ws.klippy.gcode_script(
                    f"SET_MATERIAL LANE={lane_name} MATERIAL={new_material}"
                )
                logging.info(f"AFC: SET_MATERIAL LANE={lane_name} MATERIAL={new_material}")

        self._close_edit_popup()

    # ------------------------------------------------------------------ #
    #  Selection / temperatures                                            #
    # ------------------------------------------------------------------ #

    def _select_filament(self, widget, slot_idx):
        """Select a filament slot. If already selected and non-empty, open the edit popup."""
        # Second click on an already-selected non-empty slot → open popup
        if self.selected_filament == slot_idx:
            if self.slot_materials.get(slot_idx) or self.slot_has_filament.get(slot_idx):
                self._open_edit_popup(slot_idx)
            return

        for idx, btn in self.filament_buttons.items():
            btn.get_style_context().remove_class("filament-selected")
            stack = self.slot_icon_stacks.get(idx)
            if stack:
                stack.set_visible_child_name("spool")

        widget.get_style_context().add_class("filament-selected")
        self.selected_filament = slot_idx

        non_empty = bool(self.slot_materials.get(slot_idx) or self.slot_has_filament.get(slot_idx))
        if non_empty:
            stack = self.slot_icon_stacks.get(slot_idx)
            if stack:
                stack.set_visible_child_name("pencil")

        self._load_btn.set_sensitive(non_empty)
        self._unload_btn.set_sensitive(non_empty)

    # ------------------------------------------------------------------ #
    #  Unload                                                              #
    # ------------------------------------------------------------------ #

    def _load_filament(self, _widget):
        """Load the selected lane via AFC CHANGE_TOOL."""
        lane_name = self.slot_lane_names.get(self.selected_filament)
        if lane_name:
            self.afc_change_tool(lane_name)

    def _unload_filament(self, _widget):
        """Unload the active filament via AFC TOOL_UNLOAD."""
        self.afc_tool_unload()

    # ------------------------------------------------------------------ #
    #  AFC integration                                                     #
    # ------------------------------------------------------------------ #

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
            result['result']['status:']['AFC']
        """
        self._screen.apiclient.send_request(
            "printer/afc/status",
            callback,
        )
