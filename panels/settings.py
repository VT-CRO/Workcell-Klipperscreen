import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Settings")
        super().__init__(screen, title)
        self.printers = self.settings = self.langs = {}
        self.menu = ['settings_menu']
        options = self._config.get_configurable_options().copy()
        options.append({"printers": {
            "name": _("Printer Connections"),
            "type": "menu",
            "menu": "printers"
        }})
        options.append({"lang": {
            "name": _("Language"),
            "type": "menu",
            "menu": "lang"
        }})
        self.labels['settings_menu'] = self._gtk.ScrolledWindow()
        self.labels['settings'] = Gtk.Grid()
        self.labels['settings_menu'].add(self.labels['settings'])
        for option in options:
            name = list(option)[0]
            self.add_option('settings', self.settings, name, option[name])

        self.labels['lang_menu'] = self._gtk.ScrolledWindow()
        self.labels['lang'] = Gtk.Grid()
        self.labels['lang_menu'].add(self.labels['lang'])
        for lang in ["system_lang", *self._config.lang_list]:
            self.langs[lang] = {
                "name": lang,
                "type": "button",
                "callback": self._screen.change_language,
            }
            self.add_option("lang", self.langs, lang, self.langs[lang])

        self.labels['printers_menu'] = self._gtk.ScrolledWindow()
        self.labels['printers'] = Gtk.Grid()
        self.labels['printers_menu'].add(self.labels['printers'])
        for printer in self._config.get_printers():
            pname = list(printer)[0]
            self.printers[pname] = {
                "name": pname,
                "section": f"printer {pname}",
                "type": "printer",
                "moonraker_host": printer[pname]['moonraker_host'],
                "moonraker_port": printer[pname]['moonraker_port'],
            }
            self.add_option("printers", self.printers, pname, self.printers[pname])

        button1 = self.create_rounded_button(None, "Back", self._screen._menu_go_back)
        self.content.add(button1)
        self.content.add(self.labels['settings_menu'])
        
    def create_rounded_button(self, icon_path, label_text, callback):
        button = Gtk.Button()
        button.get_style_context().add_class("rounded-button")
        if label_text == "Print":
            button.get_style_context().add_class("print-button")
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        if icon_path:
            image = Gtk.Image.new_from_file(icon_path)
            image.set_valign(Gtk.Align.CENTER)
            vbox.pack_start(image, True, True, 0)

        label = Gtk.Label(label=label_text)
        label.set_valign(Gtk.Align.CENTER)
        label.set_halign(Gtk.Align.CENTER)
        vbox.pack_start(label, False, False, 0)

        vbox.set_valign(Gtk.Align.CENTER)
        button.add(vbox)
        button.connect("clicked", callback)
        return button
