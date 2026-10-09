import wx

try:
    from .trigger_core import hotkey_description, parse_hotkey_description, trigger_keys
except ImportError:
    from trigger_core import hotkey_description, parse_hotkey_description, trigger_keys

def system_colour(colour_id):
    return wx.SystemSettings.GetColour(colour_id)

class TriggerKeyPickerDialog(wx.Dialog):
    """Compact aligned trigger palette. Supports modifiers + up to four keys."""

    MAX_KEYS = 4
    GRID_COLUMNS = 9
    CELL_WIDTH = 42
    CELL_HEIGHT = 25
    GAP = 4

    def __init__(self, parent, current_value):
        super().__init__(
            parent,
            title="Select Key",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        # Width is matched to the 9-column LETTER grid.
        # Vertical scrolling remains available for the lower sections.
        self.SetMinSize((460, 430))
        self.SetSize((470, 520))

        self.modifier_checks = {}
        self.selected_keys = []
        self.key_buttons = {}

        root = wx.BoxSizer(wx.VERTICAL)

        preview_box = wx.StaticBox(self, label=" Selected Trigger ")
        preview_sizer = wx.StaticBoxSizer(preview_box, wx.VERTICAL)
        self.preview = wx.StaticText(preview_box, label="")
        preview_font = self.preview.GetFont()
        preview_font.SetWeight(wx.FONTWEIGHT_BOLD)
        preview_font.SetPointSize(10)
        self.preview.SetFont(preview_font)
        preview_sizer.Add(self.preview, 0, wx.ALL, 6)
        root.Add(
            preview_sizer,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
            6,
        )

        scroll = wx.ScrolledWindow(self, style=wx.VSCROLL)
        scroll.SetScrollRate(0, 10)
        body = wx.BoxSizer(wx.VERTICAL)

        # Every section is laid out on the same 9-column baseline.
        self._add_modifier_section(scroll, body)

        self._add_rows_section(
            scroll,
            body,
            "LETTERS",
            self._single_key_rows(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")),
        )
        self._add_rows_section(
            scroll,
            body,
            "NUMBERS",
            self._single_key_rows(list("0123456789")),
        )
        self._add_equal_five_section(
            scroll,
            body,
            "SPECIAL",
            [
                ["Enter", "Space", "Tab", "Esc", "Delete"],
                ["Backspace"],
            ],
        )
        self._add_equal_five_section(
            scroll,
            body,
            "ARROWS / NAVIGATION",
            [
                ["Left", "Up", "Down", "Right", "Home"],
                ["End", "PageUp", "PageDown", "Insert"],
            ],
        )
        self._add_rows_section(
            scroll,
            body,
            "FUNCTION",
            self._single_key_rows(
                ["F{}".format(i) for i in range(1, 25)]
            ),
        )

        scroll.SetSizer(body)
        scroll.FitInside()
        root.Add(scroll, 1, wx.EXPAND | wx.ALL, 6)

        footer = wx.BoxSizer(wx.HORIZONTAL)
        self.selection_count = wx.StaticText(self, label="0 / 4 keys")
        self.selection_count.SetForegroundColour(
            system_colour(wx.SYS_COLOUR_GRAYTEXT)
        )
        footer.Add(self.selection_count, 0, wx.ALIGN_CENTER_VERTICAL)
        footer.AddStretchSpacer(1)

        apply_button = wx.Button(self, wx.ID_OK, "Apply", size=(70, 27))
        cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel", size=(70, 27))
        apply_button.Bind(wx.EVT_BUTTON, self.on_apply)

        footer.Add(apply_button, 0, wx.RIGHT, 5)
        footer.Add(cancel_button, 0)

        root.Add(
            footer,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            6,
        )

        self.SetSizer(root)

        self._load_current(current_value)
        self.update_preview()

        # Keep the complete 9-column width visible on the current monitor.
        display_index = wx.Display.GetFromWindow(parent)
        if display_index == wx.NOT_FOUND:
            display_index = 0

        work_area = wx.Display(display_index).GetClientArea()
        target_width = min(470, max(460, work_area.GetWidth() - 30))
        target_height = min(520, max(430, work_area.GetHeight() - 80))
        self.SetSize((target_width, target_height))
        self.CentreOnParent()

    def _section_title(self, parent, text):
        label = wx.StaticText(parent, label=text)
        font = label.GetFont()
        font.SetPointSize(7)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        label.SetFont(font)
        label.SetForegroundColour(
            system_colour(wx.SYS_COLOUR_GRAYTEXT)
        )
        return label

    def _span_width(self, span):
        return (
            self.CELL_WIDTH * span
            + self.GAP * max(0, span - 1)
        )

    def _single_key_rows(self, keys):
        rows = []
        for start in range(0, len(keys), self.GRID_COLUMNS):
            chunk = keys[start:start + self.GRID_COLUMNS]
            rows.append([(key, 1) for key in chunk])
        return rows

    def _add_modifier_section(self, parent, sizer):
        sizer.Add(
            self._section_title(parent, "MODIFIERS"),
            0,
            wx.LEFT | wx.TOP,
            6,
        )

        row = wx.BoxSizer(wx.HORIZONTAL)

        for index, (key, label) in enumerate(
            (
                ("ctrl", "Ctrl"),
                ("alt", "Alt"),
                ("shift", "Shift"),
                ("win", "Win"),
            )
        ):
            button = wx.ToggleButton(
                parent,
                label=label,
                size=(self._span_width(2), self.CELL_HEIGHT),
            )
            button.Bind(
                wx.EVT_TOGGLEBUTTON,
                self.on_modifier_changed,
            )
            self.modifier_checks[key] = button
            row.Add(button, 0)

            if index < 3:
                row.AddSpacer(self.GAP)

        sizer.Add(
            row,
            0,
            wx.LEFT | wx.TOP | wx.BOTTOM,
            6,
        )

    def _add_rows_section(self, parent, sizer, title, rows):
        sizer.Add(
            self._section_title(parent, title),
            0,
            wx.LEFT | wx.TOP,
            6,
        )

        section = wx.BoxSizer(wx.VERTICAL)

        for row_items in rows:
            row = wx.BoxSizer(wx.HORIZONTAL)
            used_columns = 0

            for item_index, (key, span) in enumerate(row_items):
                span = max(1, min(self.GRID_COLUMNS, int(span)))
                used_columns += span

                button = wx.ToggleButton(
                    parent,
                    label=key,
                    size=(
                        self._span_width(span),
                        self.CELL_HEIGHT,
                    ),
                )
                button.Bind(
                    wx.EVT_TOGGLEBUTTON,
                    self.on_key_clicked,
                )
                self.key_buttons[key.upper()] = button
                row.Add(button, 0)

                if item_index < len(row_items) - 1:
                    row.AddSpacer(self.GAP)

            # Preserve the common 9-column baseline even on short final rows.
            remaining = self.GRID_COLUMNS - used_columns
            if remaining > 0:
                if row_items:
                    row.AddSpacer(self.GAP)
                row.AddSpacer(self._span_width(remaining))

            section.Add(row, 0, wx.BOTTOM, self.GAP)

        sizer.Add(
            section,
            0,
            wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM,
            6,
        )

    def _add_equal_five_section(self, parent, sizer, title, rows):
        """Lay out each row as five equal-width slots across the common content width."""
        sizer.Add(
            self._section_title(parent, title),
            0,
            wx.LEFT | wx.TOP,
            6,
        )

        section = wx.BoxSizer(wx.VERTICAL)

        # Match the overall width of the 9-column LETTER grid.
        total_width = (
            self.CELL_WIDTH * self.GRID_COLUMNS
            + self.GAP * (self.GRID_COLUMNS - 1)
        )
        cell_width = (
            total_width - self.GAP * 4
        ) // 5

        for row_items in rows:
            row = wx.BoxSizer(wx.HORIZONTAL)

            for index in range(5):
                if index < len(row_items):
                    key = row_items[index]
                    button = wx.ToggleButton(
                        parent,
                        label=key,
                        size=(cell_width, self.CELL_HEIGHT),
                    )
                    button.Bind(
                        wx.EVT_TOGGLEBUTTON,
                        self.on_key_clicked,
                    )
                    self.key_buttons[key.upper()] = button
                    row.Add(button, 0)
                else:
                    row.AddSpacer(cell_width)

                if index < 4:
                    row.AddSpacer(self.GAP)

            section.Add(row, 0, wx.BOTTOM, self.GAP)

        sizer.Add(
            section,
            0,
            wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM,
            6,
        )

    def _load_current(self, current_value):
        try:
            trigger = parse_hotkey_description(current_value)
        except Exception:
            trigger = {
                "ctrl": False,
                "alt": False,
                "shift": False,
                "win": False,
                "keys": [],
            }

        for name, button in self.modifier_checks.items():
            button.SetValue(bool(trigger.get(name, False)))

        self.selected_keys = []

        for key in trigger_keys(trigger):
            if (
                key in self.key_buttons
                and len(self.selected_keys) < self.MAX_KEYS
            ):
                self.selected_keys.append(key)
                self.key_buttons[key].SetValue(True)

    def on_modifier_changed(self, _event):
        self.update_preview()

    def on_key_clicked(self, event):
        clicked = event.GetEventObject()
        key = clicked.GetLabel().upper()

        if clicked.GetValue():
            if key not in self.selected_keys:
                if len(self.selected_keys) >= self.MAX_KEYS:
                    clicked.SetValue(False)
                    wx.MessageBox(
                        "Up to 4 keys can be selected.",
                        "Select Key",
                        wx.OK | wx.ICON_INFORMATION,
                        self,
                    )
                    return
                self.selected_keys.append(key)
        else:
            if key in self.selected_keys:
                self.selected_keys.remove(key)

        self.update_preview()

    def get_trigger(self):
        if not self.selected_keys:
            raise ValueError("Select at least one trigger key")

        keys = list(self.selected_keys[: self.MAX_KEYS])

        return {
            "enabled": True,
            "ctrl": self.modifier_checks["ctrl"].GetValue(),
            "alt": self.modifier_checks["alt"].GetValue(),
            "shift": self.modifier_checks["shift"].GetValue(),
            "win": self.modifier_checks["win"].GetValue(),
            "key": keys[0],
            "keys": keys,
        }

    def update_preview(self):
        self.selection_count.SetLabel(
            "{} / {} keys".format(
                len(self.selected_keys),
                self.MAX_KEYS,
            )
        )

        try:
            self.preview.SetLabel(
                hotkey_description(self.get_trigger())
            )
        except Exception:
            self.preview.SetLabel("Select 1-4 keys")

    def on_apply(self, _event):
        try:
            self.get_trigger()
        except Exception as exc:
            wx.MessageBox(
                str(exc),
                "Select Key",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return

        self.EndModal(wx.ID_OK)


