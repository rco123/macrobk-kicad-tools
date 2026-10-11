import copy
import os
import sys
import uuid

import wx
import wx.stc as stc

try:
    from .key_picker import TriggerKeyPickerDialog
    from . import trigger_core as core
except ImportError:
    from key_picker import TriggerKeyPickerDialog
    import trigger_core as core

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
from .lifecycle import engine
core = engine(core)
ICON_DIR = os.path.join(PLUGIN_DIR, "icons")
LOG_PATH = core.LOG_PATH
_manager_frame = globals().get("_manager_frame")

def system_colour(colour_id):
    return wx.SystemSettings.GetColour(colour_id)

def is_dark_theme():
    colour = system_colour(wx.SYS_COLOUR_WINDOW)
    return (colour.Red() * 299 + colour.Green() * 587 + colour.Blue() * 114) < 128000

def icon_bitmap(name, size=20):
    path = os.path.join(ICON_DIR, "{}.png".format(name))
    if os.path.isfile(path):
        image = wx.Image(path, wx.BITMAP_TYPE_PNG)
        if image.IsOk() and (image.GetWidth() != size or image.GetHeight() != size):
            image = image.Scale(size, size, wx.IMAGE_QUALITY_HIGH)
        if image.IsOk():
            return wx.Bitmap(image)
    fallback = {
        "add": wx.ART_PLUS,
        "duplicate": wx.ART_COPY,
        "delete": wx.ART_DELETE,
        "play": wx.ART_GO_FORWARD,
        "save": wx.ART_FILE_SAVE,
        "copy": wx.ART_COPY,
        "clear": wx.ART_DELETE,
        "error": wx.ART_ERROR,
        "success": wx.ART_TICK_MARK,
        "result": wx.ART_REPORT_VIEW,
        "execute": wx.ART_EXECUTABLE_FILE,
        "plugin": wx.ART_INFORMATION,
    }.get(name, wx.ART_NORMAL_FILE)
    return wx.ArtProvider.GetBitmap(fallback, wx.ART_BUTTON, (size, size))

def style_button(button, icon_name=None, min_width=88):
    if icon_name:
        button.SetBitmap(icon_bitmap(icon_name, 16))
        button.SetBitmapMargins((6, 2))
    button.SetMinSize((min_width, 32))
    return button

def action_icon_name(action):
    explicit = str(action.get("icon", "")).strip()
    if explicit:
        return explicit
    name = str(action.get("name", "")).lower()
    if "drc" in name or "rule" in name:
        return "drc"
    if "3d" in name or "viewer" in name:
        return "cube"
    if "setup" in name or "setting" in name:
        return "gear"
    return "execute"

def get_manager_frame():
    service = core.get_service()
    manager = service.manager or _manager_frame
    return manager if manager is not None and bool(manager) and not manager.IsBeingDeleted() else None

class MacroBKPluginManager(wx.Frame):
    def __init__(self, parent):
        # Keep the Manager above its own PCB Editor frame during Run Test.
        # FLOAT_ON_PARENT does not make this window globally always-on-top;
        # native KiCad dialogs must still be able to appear above it.
        super().__init__(
            parent,
            title="MacroBK PCB Tools",
            size=(1000, 660),
            style=wx.DEFAULT_FRAME_STYLE | wx.FRAME_FLOAT_ON_PARENT,
        )
        self.SetMinSize((960, 620))
        self.SetIcon(wx.Icon(icon_bitmap("plugin", 32)))
        self._blink_timer = None
        self._loading_action = False
        self.actions = copy.deepcopy(core.CONFIG.get("actions", []))
        self.selected_index = 0

        background = system_colour(wx.SYS_COLOUR_WINDOW)
        panel_background = system_colour(wx.SYS_COLOUR_BTNFACE)
        text_colour = system_colour(wx.SYS_COLOUR_WINDOWTEXT)
        muted_colour = system_colour(wx.SYS_COLOUR_GRAYTEXT)
        divider_colour = system_colour(wx.SYS_COLOUR_3DSHADOW)

        root_panel = wx.Panel(self)
        root_panel.SetBackgroundColour(background)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        header = wx.Panel(root_panel)
        header.SetBackgroundColour(panel_background)
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        header_icon = wx.StaticBitmap(header, bitmap=icon_bitmap("plugin", 28))
        header_sizer.Add(header_icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 16)
        title_stack = wx.BoxSizer(wx.VERTICAL)
        product_title = wx.StaticText(header, label="MacroBK PCB Tools")
        product_font = product_title.GetFont()
        product_font.SetPointSize(13)
        product_font.SetWeight(wx.FONTWEIGHT_BOLD)
        product_title.SetFont(product_font)
        product_subtitle = wx.StaticText(
            header, label="KiCad automation actions and input monitoring"
        )
        product_subtitle.SetForegroundColour(muted_colour)
        title_stack.Add(product_title, 0)
        title_stack.Add(product_subtitle, 0, wx.TOP, 2)
        header_sizer.Add(title_stack, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 12)
        header.SetSizer(header_sizer)
        root_sizer.Add(header, 0, wx.EXPAND)
        root_sizer.Add(wx.StaticLine(root_panel), 0, wx.EXPAND)

        content_sizer = wx.BoxSizer(wx.HORIZONTAL)
        left_panel = wx.Panel(root_panel)
        left_panel.SetBackgroundColour(panel_background)
        left_panel.SetMinSize((360, -1))
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        left_title = wx.StaticText(left_panel, label="REGISTERED ACTIONS")
        left_title_font = left_title.GetFont()
        left_title_font.SetPointSize(9)
        left_title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        left_title.SetFont(left_title_font)
        left_title.SetForegroundColour(muted_colour)
        left_sizer.Add(left_title, 0, wx.LEFT | wx.RIGHT | wx.TOP, 14)

        self.action_images = wx.ImageList(20, 20)
        self.action_image_indexes = {}
        for name in ("drc", "cube", "gear", "execute"):
            self.action_image_indexes[name] = self.action_images.Add(icon_bitmap(name, 20))
        self.action_list = wx.ListCtrl(
            left_panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE,
        )
        self.action_list.SetMinSize((336, 130))
        self.action_list.AssignImageList(self.action_images, wx.IMAGE_LIST_SMALL)
        self.action_list.InsertColumn(0, "Name", width=150)
        self.action_list.InsertColumn(1, "Trigger", width=180)
        self.action_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_action_selected)
        self.action_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_action_rename)
        left_sizer.Add(self.action_list, 1, wx.EXPAND | wx.ALL, 10)

        action_buttons = wx.BoxSizer(wx.HORIZONTAL)
        add_button = style_button(wx.Button(left_panel, label="Add"), "add", 72)
        duplicate_button = style_button(
            wx.Button(left_panel, label="Duplicate"), "duplicate", 94
        )
        delete_button = style_button(wx.Button(left_panel, label="Delete"), "delete", 78)
        delete_button.SetForegroundColour(wx.Colour(170, 55, 55))
        add_button.Bind(wx.EVT_BUTTON, self.on_add_action)
        duplicate_button.Bind(wx.EVT_BUTTON, self.on_duplicate_action)
        delete_button.Bind(wx.EVT_BUTTON, self.on_delete_action)
        action_buttons.Add(add_button, 0, wx.RIGHT, 6)
        action_buttons.Add(duplicate_button, 0, wx.RIGHT, 6)
        action_buttons.Add(delete_button, 0)
        left_sizer.Add(action_buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        monitor_box = wx.StaticBox(left_panel, label=" Input Monitor ")
        monitor_sizer = wx.StaticBoxSizer(monitor_box, wx.VERTICAL)
        self.keyboard_led, self.keyboard_status_label = self.create_monitor_row(
            monitor_box, monitor_sizer, "keyboard", "Keyboard", core.get_keyboard_status()
        )
        self.phone_led, self.phone_status_label = self.create_monitor_row(
            monitor_box, monitor_sizer, "phone", "Phone", core.get_phone_status()
        )
        self.signal_source = wx.StaticText(monitor_box, label="Waiting for input")
        self.signal_source.SetForegroundColour(muted_colour)
        monitor_sizer.Add(self.signal_source, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        left_sizer.Add(monitor_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        left_sizer.Add(
            wx.StaticText(left_panel, label="Trigger Key"),
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            12,
        )

        trigger_row = wx.BoxSizer(wx.HORIZONTAL)

        self.trigger_picker_button = style_button(
            wx.Button(left_panel, label=""),
            "keyboard",
            44,
        )
        self.trigger_picker_button.SetToolTip("Select trigger key")
        self.trigger_picker_button.Bind(wx.EVT_BUTTON, self.on_select_trigger_key)

        self.trigger_text = wx.TextCtrl(
            left_panel,
            style=wx.TE_READONLY,
        )
        self.trigger_text.SetMinSize((-1, 32))

        trigger_row.Add(self.trigger_picker_button, 0, wx.RIGHT, 6)
        trigger_row.Add(self.trigger_text, 1, wx.EXPAND)

        left_sizer.Add(
            trigger_row,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
            10,
        )

        register_button = style_button(
            wx.Button(left_panel, label="Register"),
            "keyboard",
            100,
        )
        register_button.Bind(wx.EVT_BUTTON, self.on_register)
        left_sizer.Add(register_button, 0, wx.EXPAND | wx.ALL, 10)
        left_panel.SetSizer(left_sizer)

        right_panel = wx.Panel(root_panel)
        right_panel.SetBackgroundColour(background)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        self.action_title = wx.StaticText(right_panel, label="Open DRC")
        action_title_font = self.action_title.GetFont()
        action_title_font.SetPointSize(16)
        action_title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.action_title.SetFont(action_title_font)
        self.action_trigger_summary = wx.StaticText(right_panel, label="Ctrl + Win + F12")
        self.action_trigger_summary.SetForegroundColour(muted_colour)
        right_sizer.Add(self.action_title, 0, wx.LEFT | wx.RIGHT | wx.TOP, 16)
        right_sizer.Add(self.action_trigger_summary, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 16)

        # Python Script and Result are visible at the same time.
        # The center divider can be dragged left/right.
        #
        # Design:
        # - outer border is thin and subdued
        # - center divider uses the same system shadow tone
        # - top/bottom inset keeps the center divider from touching the frame
        work_frame = wx.Panel(right_panel, style=wx.BORDER_SIMPLE)
        work_frame.SetBackgroundColour(background)
        work_frame_sizer = wx.BoxSizer(wx.VERTICAL)

        self.work_splitter = wx.SplitterWindow(
            work_frame,
            style=wx.SP_LIVE_UPDATE | wx.BORDER_NONE,
        )
        self.work_splitter.SetBackgroundColour(divider_colour)
        self.work_splitter.SetMinimumPaneSize(180)
        # wx.SplitterWindow on KiCad's wxPython build does not provide SetSashSize().
        # Keep the native sash thickness for compatibility.

        execute_panel = wx.Panel(self.work_splitter)
        result_panel = wx.Panel(self.work_splitter)
        execute_panel.SetBackgroundColour(background)
        result_panel.SetBackgroundColour(background)

        execute_sizer = wx.BoxSizer(wx.VERTICAL)
        script_title = wx.StaticText(execute_panel, label="Python Script")
        script_title_font = script_title.GetFont()
        script_title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        script_title.SetFont(script_title_font)
        execute_sizer.Add(script_title, 0, wx.ALL, 12)

        self.script_text = stc.StyledTextCtrl(execute_panel, style=wx.BORDER_SIMPLE)
        self.configure_python_editor(self.script_text)
        execute_sizer.Add(
            self.script_text,
            1,
            wx.EXPAND | wx.LEFT | wx.RIGHT,
            12,
        )

        execute_controls = wx.BoxSizer(wx.HORIZONTAL)
        self.test_button = style_button(
            wx.Button(execute_panel, label="Run Test"),
            "play",
            120,
        )
        self.test_button.Bind(wx.EVT_BUTTON, self.on_test_run)
        self.test_button.SetDefault()

        self.stop_button = wx.Button(execute_panel, label="Stop")
        self.stop_button.SetMinSize((84, 32))
        self.stop_button.Enable(False)
        self.stop_button.Bind(wx.EVT_BUTTON, self.on_stop_test)

        self.save_button = wx.Button(execute_panel, label="Save")
        self.save_button.SetMinSize((84, 32))
        self.save_button.Bind(wx.EVT_BUTTON, self.on_save)

        self.test_status_label = wx.StaticText(execute_panel, label="IDLE")
        status_font = self.test_status_label.GetFont()
        status_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.test_status_label.SetFont(status_font)

        execute_controls.Add(self.test_button, 0, wx.RIGHT, 8)
        execute_controls.Add(self.stop_button, 0, wx.RIGHT, 8)
        execute_controls.Add(self.save_button, 0, wx.RIGHT, 14)
        execute_controls.Add(
            self.test_status_label,
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        execute_sizer.Add(execute_controls, 0, wx.ALL, 12)
        execute_panel.SetSizer(execute_sizer)

        result_sizer = wx.BoxSizer(wx.VERTICAL)

        result_title = wx.StaticText(result_panel, label="Result")
        result_title_font = result_title.GetFont()
        result_title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        result_title.SetFont(result_title_font)
        result_sizer.Add(result_title, 0, wx.ALL, 12)

        self.result_text = stc.StyledTextCtrl(
            result_panel,
            style=wx.BORDER_SIMPLE,
        )
        self.configure_log_editor(self.result_text)
        result_sizer.Add(
            self.result_text,
            1,
            wx.EXPAND | wx.LEFT | wx.RIGHT,
            12,
        )

        result_controls = wx.BoxSizer(wx.HORIZONTAL)
        result_controls.AddStretchSpacer(1)

        copy_button = style_button(
            wx.Button(result_panel, label="Copy"),
            "copy",
            84,
        )
        clear_button = style_button(
            wx.Button(result_panel, label="Clear"),
            "clear",
            84,
        )

        copy_button.Bind(wx.EVT_BUTTON, self.on_copy)
        clear_button.Bind(wx.EVT_BUTTON, self.on_clear)

        result_controls.Add(copy_button, 0, wx.RIGHT, 8)
        result_controls.Add(clear_button, 0)

        result_sizer.Add(
            result_controls,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM,
            12,
        )
        result_panel.SetSizer(result_sizer)

        self.work_splitter.SplitVertically(
            execute_panel,
            result_panel,
        )
        self.work_splitter.SetSashGravity(0.5)

        def set_initial_split():
            width = self.work_splitter.GetClientSize().GetWidth()
            if width > 0:
                self.work_splitter.SetSashPosition(width // 2)

        wx.CallAfter(set_initial_split)

        # Top/bottom spacing shortens the visible center divider.
        work_frame_sizer.Add(
            self.work_splitter,
            1,
            wx.EXPAND | wx.TOP | wx.BOTTOM,
            8,
        )
        work_frame.SetSizer(work_frame_sizer)

        right_sizer.Add(
            work_frame,
            1,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            12,
        )
        right_panel.SetSizer(right_sizer)
        content_sizer.Add(left_panel, 0, wx.EXPAND)
        content_sizer.Add(wx.StaticLine(root_panel, style=wx.LI_VERTICAL), 0, wx.EXPAND)
        content_sizer.Add(right_panel, 1, wx.EXPAND)
        root_sizer.Add(content_sizer, 1, wx.EXPAND)

        root_panel.SetSizer(root_sizer)
        self.status_bar = self.CreateStatusBar(4)
        self.status_bar.SetStatusWidths([-2, -2, -2, -1])
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.CentreOnParent()
        self.refresh_action_list()
        selected_id = str(core.CONFIG.get("selected_action_id", ""))
        self.selected_index = next(
            (i for i, item in enumerate(self.actions) if item["id"] == selected_id), 0
        )
        self.action_list.Select(self.selected_index)
        self.load_action(self.selected_index)
        # Result shows only current script output/errors. Internal diagnostics stay in the log file.
        self.update_status_bar()

    def create_monitor_row(self, parent, sizer, icon_name, label, status):
        row = wx.BoxSizer(wx.HORIZONTAL)
        icon = wx.StaticBitmap(parent, bitmap=icon_bitmap(icon_name, 18))
        led = wx.StaticText(parent, label="●")
        led_font = led.GetFont()
        led_font.SetPointSize(14)
        led.SetFont(led_font)
        status_label = wx.StaticText(parent, label="{}  {}".format(label, status))
        row.Add(icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        row.Add(led, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(status_label, 1, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(row, 0, wx.EXPAND | wx.ALL, 8)
        self.set_led_colour(led, status)
        return led, status_label

    def set_led_colour(self, control, status):
        colours = {
            "Ready": wx.Colour(39, 174, 96),
            "Conflict": wx.Colour(230, 126, 34),
            "Error": wx.Colour(192, 57, 43),
            "Port Error": wx.Colour(192, 57, 43),
            "Disabled": wx.Colour(127, 140, 141),
            "Phone Only": wx.Colour(52, 152, 219),
        }
        control.SetForegroundColour(colours.get(str(status), wx.Colour(127, 140, 141)))

    def configure_python_editor(self, editor):
        dark = is_dark_theme()
        foreground = "#E7EAF0" if dark else "#20242A"
        background = "#1F2329" if dark else "#FBFCFE"
        editor.SetLexer(stc.STC_LEX_PYTHON)
        editor.StyleSetSpec(stc.STC_STYLE_DEFAULT, "face:Consolas,size:10,fore:{},back:{}".format(foreground, background))
        editor.StyleClearAll()
        editor.StyleSetSpec(stc.STC_P_COMMENTLINE, "fore:#6A9955,italic")
        editor.StyleSetSpec(stc.STC_P_NUMBER, "fore:#B477DB")
        editor.StyleSetSpec(stc.STC_P_STRING, "fore:#CE9178")
        editor.StyleSetSpec(stc.STC_P_CHARACTER, "fore:#CE9178")
        editor.StyleSetSpec(stc.STC_P_WORD, "fore:#569CD6,bold")
        editor.SetKeyWords(0, "and as assert async await break class continue def del elif else except False finally for from global if import in is lambda None nonlocal not or pass raise return True try while with yield")
        editor.SetMarginType(0, stc.STC_MARGIN_NUMBER)
        editor.SetMarginWidth(0, 42)
        editor.StyleSetSpec(stc.STC_STYLE_LINENUMBER, "face:Consolas,size:9,fore:#7F8792,back:{}".format(background))
        editor.SetTabWidth(4)
        editor.SetUseTabs(False)
        editor.SetIndent(4)
        editor.SetViewWhiteSpace(False)
        editor.SetCaretLineVisible(True)
        editor.SetCaretLineBackground("#2A3038" if dark else "#EEF3FA")
        editor.SetScrollWidthTracking(True)

    def configure_log_editor(self, editor):
        dark = is_dark_theme()
        foreground = "#E7EAF0" if dark else "#20242A"
        background = "#171A1F" if dark else "#FBFCFE"
        editor.SetLexer(stc.STC_LEX_NULL)
        editor.StyleSetSpec(0, "face:Consolas,size:9,fore:{},back:{}".format(foreground, background))
        editor.StyleSetSpec(1, "face:Consolas,size:9,fore:#27AE60,back:{},bold".format(background))
        editor.StyleSetSpec(2, "face:Consolas,size:9,fore:#E74C3C,back:{},bold".format(background))
        editor.SetMarginWidth(0, 0)
        editor.SetReadOnly(True)

    def style_log_range(self, start, text):
        style = 2 if "ERROR" in text or "Traceback" in text else 1 if "SUCCESS" in text else 0
        self.result_text.StartStyling(start)
        self.result_text.SetStyling(len(text), style)

    def load_file_log(self):
        try:
            with open(LOG_PATH, "r", encoding="utf-8") as file:
                for line in file.read().splitlines():
                    self.append_result(line)
        except Exception:
            pass

    def append_result(self, line):
        text = str(line) + "\n"
        start = self.result_text.GetTextLength()
        self.result_text.SetReadOnly(False)
        self.result_text.AppendText(text)
        self.style_log_range(start, text)
        self.result_text.SetReadOnly(True)
        self.result_text.GotoPos(self.result_text.GetTextLength())

    def refresh_action_list(self):
        self.action_list.Freeze()
        self.action_list.DeleteAllItems()
        for action in self.actions:
            icon_name = action_icon_name(action)
            image_index = self.action_image_indexes.get(icon_name, self.action_image_indexes["execute"])
            row = self.action_list.InsertItem(self.action_list.GetItemCount(), action["name"], image_index)
            self.action_list.SetItem(row, 1, core.hotkey_description(action.get("trigger", {})))
        self.action_list.Thaw()

    def store_current_action(self):
        if self._loading_action or not self.actions:
            return
        action = self.actions[self.selected_index]
        try:
            action["trigger"] = self.read_trigger()
        except Exception:
            pass
        action["action"] = {"type": "python", "script": self.script_text.GetValue()}

    def load_action(self, index):
        if not 0 <= index < len(self.actions):
            return
        self._loading_action = True
        self.selected_index = index
        action = self.actions[index]
        trigger_value = core.hotkey_description(action.get("trigger", {}))
        self.action_title.SetLabel(action["name"])
        self.action_trigger_summary.SetLabel(trigger_value)
        self.trigger_text.SetValue(trigger_value)
        self.script_text.SetValue(str(action.get("action", {}).get("script", "")))
        self._loading_action = False
        self.update_status_bar()

    def on_action_selected(self, event):
        new_index = event.GetIndex()
        if new_index == self.selected_index:
            return
        self.store_current_action()
        self.load_action(new_index)

    def on_action_rename(self, event):
        index = event.GetIndex()
        current = self.actions[index]["name"]
        dialog = wx.TextEntryDialog(self, "Action name", "Rename Action", current)
        try:
            if dialog.ShowModal() == wx.ID_OK and dialog.GetValue().strip():
                self.actions[index]["name"] = dialog.GetValue().strip()
                self.refresh_action_list()
                self.action_list.Select(index)
                self.load_action(index)
        finally:
            dialog.Destroy()

    def on_add_action(self, _event):
        self.store_current_action()
        new_action = {
            "id": "action-" + uuid.uuid4().hex[:8],
            "name": "New Action",
            "icon": "execute",
            "trigger": copy.deepcopy(core.DEFAULT_CONFIG["trigger"]),
            "phone": copy.deepcopy(core.DEFAULT_CONFIG["phone"]),
            "action": {"type": "python", "script": "# Enter KiCad Python here\n"},
        }
        self.actions.append(new_action)
        self.refresh_action_list()
        self.action_list.Select(len(self.actions) - 1)
        self.load_action(len(self.actions) - 1)

    def on_duplicate_action(self, _event):
        self.store_current_action()
        duplicate = copy.deepcopy(self.actions[self.selected_index])
        duplicate["id"] = "action-" + uuid.uuid4().hex[:8]
        duplicate["name"] = duplicate["name"] + " Copy"
        self.actions.append(duplicate)
        self.refresh_action_list()
        self.action_list.Select(len(self.actions) - 1)
        self.load_action(len(self.actions) - 1)

    def on_delete_action(self, _event):
        if len(self.actions) <= 1:
            wx.MessageBox("At least one action must remain.", "MacroBK PCB Tools", wx.OK | wx.ICON_INFORMATION)
            return
        action = self.actions[self.selected_index]
        answer = wx.MessageBox(
            "Delete '{}'?".format(action["name"]),
            "Delete Action",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )
        if answer != wx.YES:
            return
        del self.actions[self.selected_index]
        self.selected_index = min(self.selected_index, len(self.actions) - 1)
        self.refresh_action_list()
        self.action_list.Select(self.selected_index)
        self.load_action(self.selected_index)

    def set_keyboard_status(self, status):
        self.keyboard_status_label.SetLabel("Keyboard  " + str(status))
        self.set_led_colour(self.keyboard_led, status)
        self.update_status_bar()

    def set_phone_status(self, status):
        self.phone_status_label.SetLabel("Phone  " + str(status))
        self.set_led_colour(self.phone_led, status)
        self.update_status_bar()

    def set_test_status(self, status, stoppable=True):
        label = str(status)
        self.test_status_label.SetLabel(label)

        running = label in ("RUNNING", "STOPPING")
        if hasattr(self, "test_button"):
            self.test_button.Enable(not running)
        if hasattr(self, "stop_button"):
            self.stop_button.Enable(label == "RUNNING" and bool(stoppable))

        if label == "SUCCESS":
            self.test_status_label.SetForegroundColour(wx.Colour(39, 174, 96))
        elif label == "ERROR":
            self.test_status_label.SetForegroundColour(wx.Colour(192, 57, 43))
        else:
            self.test_status_label.SetForegroundColour(system_colour(wx.SYS_COLOUR_WINDOWTEXT))

    def update_status_bar(self):
        if not hasattr(self, "status_bar"):
            return
        self.status_bar.SetStatusText("●  Plugin Ready", 0)
        self.status_bar.SetStatusText("Keyboard {}".format(core.get_keyboard_status()), 1)
        self.status_bar.SetStatusText("Phone {}".format(core.get_phone_status()), 2)
        self.status_bar.SetStatusText("{} Actions".format(len(self.actions)), 3)

    def show_result_tab(self):
        # Result pane is always visible.
        pass

    def blink_input_signal(self, source):
        led = self.keyboard_led if source == "keyboard" else self.phone_led
        led.SetForegroundColour(wx.Colour(52, 152, 219))
        self.signal_source.SetLabel("Input received from {}".format(source.title()))
        if self._blink_timer is not None:
            self._blink_timer.Stop()
        self._blink_timer = wx.CallLater(400, self.reset_input_signal)

    def reset_input_signal(self):
        self.set_led_colour(self.keyboard_led, core.get_keyboard_status())
        self.set_led_colour(self.phone_led, core.get_phone_status())
        self.signal_source.SetLabel("Waiting for input")

    def on_select_trigger_key(self, _event):
        dialog = TriggerKeyPickerDialog(self, self.trigger_text.GetValue())
        try:
            if dialog.ShowModal() == wx.ID_OK:
                trigger = dialog.get_trigger()
                value = core.hotkey_description(trigger)
                self.trigger_text.SetValue(value)
                self.action_trigger_summary.SetLabel(value)
        finally:
            dialog.Destroy()

    def read_trigger(self):
        return core.parse_hotkey_description(self.trigger_text.GetValue())

    def apply_selected_to_config(self):
        self.store_current_action()
        selected = self.actions[self.selected_index]
        core.CONFIG["actions"] = copy.deepcopy(self.actions)
        core.CONFIG["selected_action_id"] = selected["id"]
        core.CONFIG["name"] = selected["name"]
        core.CONFIG["trigger"] = copy.deepcopy(selected["trigger"])
        core.CONFIG["phone"] = copy.deepcopy(selected["phone"])
        core.CONFIG["action"] = copy.deepcopy(selected["action"])

    def on_register(self, _event):
        try:
            self.apply_selected_to_config()
            core.save_config()

            value = core.hotkey_description(core.CONFIG["trigger"])
            self.trigger_text.SetValue(value)
            self.action_trigger_summary.SetLabel(value)

            # Immediately update the Trigger column in REGISTERED ACTIONS.
            self.refresh_action_list()
            self.action_list.Select(self.selected_index)
            self.action_list.Focus(self.selected_index)

            core.log("Register requested shortcut={}".format(value))
            core.restart_hotkey_listener()
        except Exception as exc:
            self.set_keyboard_status("Error")
            core.log("Register error: " + str(exc))
            self.show_result_tab()

    def begin_test_run(self, action_id, run_id):
        self.running_test_action_id = action_id
        self.running_test_run_id = run_id
        self.set_test_status("RUNNING")

    def finish_test_run(self, action_id, run_id, status):
        if (getattr(self, "running_test_action_id", None),
                getattr(self, "running_test_run_id", None)) != (action_id, run_id):
            return
        self.set_test_status(status)
        self.running_test_action_id = None

    def on_test_run(self, _event):
        core.bind_gui_thread()
        action_id = self.actions[self.selected_index]["id"] if self.actions else "test"
        core.execute_python_script(self.script_text.GetValue(), "test", action_id)

    def on_stop_test(self, _event):
        action_id = getattr(self, "running_test_action_id", None)
        if action_id is not None and core.stop_action(action_id, "test", getattr(self, "running_test_run_id", None)):
            self.set_test_status("STOPPING")

    def on_save(self, _event):
        try:
            self.apply_selected_to_config()
            core.save_config()
            self.refresh_action_list()
            self.action_list.Select(self.selected_index)
            self.load_action(self.selected_index)
            core.restart_hotkey_listener()
        except Exception as exc:
            core.log("Save error: " + repr(exc))
            self.show_result_tab()

    def on_copy(self, _event):
        if wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(self.result_text.GetValue()))
                wx.TheClipboard.Flush()
            finally:
                wx.TheClipboard.Close()

    def on_clear(self, _event):
        self.result_text.SetReadOnly(False)
        self.result_text.ClearAll()
        self.result_text.SetReadOnly(True)

    def dispose(self):
        """Destroy only this Manager; never save config during lifecycle cleanup."""
        global _manager_frame
        if getattr(self, "_disposing", False):
            return
        self._disposing = True
        action_id = getattr(self, "running_test_action_id", None)
        if action_id is not None:
            core.stop_action(action_id, "test")
        if self._blink_timer is not None:
            self._blink_timer.Stop()
            self._blink_timer = None
        if _manager_frame is self:
            _manager_frame = None
        service = core.get_service()
        if service.manager is self:
            service.manager = None
        self.Destroy()

    def on_close(self, event):
        core.log("MANAGER CLOSE")
        self.dispose()


def show_manager():
    core.bind_gui_thread()
    global _manager_frame
    service = core.get_service()
    if not service.accepting:
        return
    if service.ui_module is not None and service.ui_module is not sys.modules[__name__]:
        return service.ui_module.show_manager()
    service.ui_module = sys.modules[__name__]
    service.attach_frame()
    _manager_frame = service.manager or _manager_frame
    if (
        _manager_frame is not None
        and bool(_manager_frame)
        and not _manager_frame.IsBeingDeleted()
    ):
        try:
            if _manager_frame.IsIconized():
                _manager_frame.Iconize(False)
            core.log("MANAGER OPEN")
            _manager_frame.Show(True)
            _manager_frame.Raise()
            _manager_frame.SetFocus()
            return
        except Exception:
            _manager_frame = None

    # Parent to the identified PCB main frame, never a transient child window.
    _manager_frame = MacroBKPluginManager(service.frame)
    service.manager = _manager_frame
    _manager_frame.Show(True)
    _manager_frame.Raise()
    _manager_frame.SetFocus()
    core.log("MANAGER OPEN")



core.set_manager_provider(get_manager_frame)
