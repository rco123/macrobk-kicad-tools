"""Appearance-owned SNAP UI.

Reads and writes are popup-free. The panel delegates to kicad_controls SNAP
APIs; the backend updates KiCad's own saved Magnetic Points values and reloads
the live settings manager. No Preferences dialog is opened.
"""
import wx

from . import kicad_controls as kc

OWNER = "MacroBK.snap-panel.v1"


def find_appearance_notebook(frame):
    signature = [wx.GetTranslation(s) for s in ("Layers", "Objects", "Nets")]
    matches = [
        w
        for w in kc.iter_controls(frame)
        if isinstance(w, wx.Notebook)
        and w.GetPageCount() >= 3
        and [w.GetPageText(i) for i in range(3)] == signature
    ]
    return matches[0] if len(matches) == 1 else None


class SnapPanel(wx.Panel):
    def __init__(self, book):
        super().__init__(book, name=OWNER)
        self.book = book
        self.disposed = False
        self.busy = False
        self.queued = False
        self.verified = None
        self.choices = {}

        sizer = wx.BoxSizer(wx.VERTICAL)
        title = wx.StaticText(self, label="Magnetic Points")
        font = title.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(font)
        sizer.Add(title, 0, wx.ALL, 10)

        for key, label in (
            ("pads", "Snap to pads"),
            ("tracks_vias", "Snap to tracks and vias"),
            ("graphics", "Snap to graphics"),
        ):
            sizer.Add(wx.StaticText(self, label=label), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
            choice = wx.Choice(self)
            choice.Enable(False)
            choice.Bind(
                wx.EVT_CHOICE,
                lambda event, setting=key: self.on_snap_choice_changed(event, setting),
            )
            self.choices[key] = choice
            sizer.Add(choice, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.status = wx.StaticText(self, label="")
        self.status_text = ""
        sizer.Add(self.status, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.SetSizer(sizer)

        book.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_page_changed)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.on_destroy)
        self.Bind(wx.EVT_SIZE, self.on_size)

    def set_status(self, text):
        self.status_text = str(text or "")
        self.status.SetLabel(self.status_text)
        self.status.Wrap(max(100, self.GetClientSize().width - 20))

    def on_size(self, event):
        event.Skip()
        if not self.disposed:
            self.set_status(self.status_text)
            self.Layout()

    def on_page_changed(self, event):
        event.Skip()
        index = event.GetSelection()
        if (
            not self.disposed
            and 0 <= index < self.book.GetPageCount()
            and self.book.GetPage(index) == self
        ):
            # Safe and popup-free: read KiCad's saved state only.
            self.refresh_from_kicad()

    def display(self, payload):
        self.verified = payload
        for key, choice in self.choices.items():
            choice.SetItems(payload["choices"][key])
            choice.SetStringSelection(payload["values"][key])
            choice.Enable(True)
        self.set_status("")
        self.Layout()

    def refresh_from_kicad(self):
        if self.disposed or self.busy or self.queued:
            return
        self.queued = True
        wx.CallAfter(self._perform, {})

    def on_snap_choice_changed(self, event, key):
        if self.disposed or self.busy or self.queued:
            return
        value = self.choices[key].GetStringSelection()
        # Do not leave an optimistic selection while KiCad applies the setting.
        if self.verified is not None:
            self.choices[key].SetStringSelection(self.verified["values"][key])
        self.queued = True
        wx.CallAfter(self._perform, {key: value})

    def _perform(self, changes):
        self.queued = False
        if self.disposed or not bool(self) or self.IsBeingDeleted():
            return
        frame = wx.GetTopLevelParent(self)
        if not bool(frame) or frame.IsBeingDeleted():
            return

        self.busy = True
        for choice in self.choices.values():
            choice.Enable(False)
        try:
            if changes:
                kc.pcb_set_snap_settings(**changes)
            payload = kc.pcb_get_snap_settings(include_choices=True)
            if not self.disposed:
                self.display(payload)
        except Exception as exc:
            if not self.disposed:
                try:
                    # Read-only getter is popup-free, so failure recovery is safe.
                    self.display(kc.pcb_get_snap_settings(include_choices=True))
                except Exception:
                    for choice in self.choices.values():
                        choice.SetSelection(wx.NOT_FOUND)
                        choice.Enable(False)
                self.set_status(str(exc))
                kc.log("SNAP request failed: " + repr(exc))
        finally:
            self.busy = False
            if not self.disposed and bool(self):
                self.Layout()

    def dispose(self):
        if self.disposed:
            return
        self.disposed = True
        if bool(self.book) and not self.book.IsBeingDeleted():
            self.book.Unbind(wx.EVT_NOTEBOOK_PAGE_CHANGED, handler=self.on_page_changed)

    def on_destroy(self, event):
        if event.GetEventObject() == self:
            self.dispose()
        event.Skip()


def attach_snap_tab(frame):
    book = find_appearance_notebook(frame)
    if book is None:
        return None
    for i in range(book.GetPageCount()):
        page = book.GetPage(i)
        if page.GetName() == OWNER:
            return page
        if book.GetPageText(i) == "SNAP":
            kc.log("SNAP attachment skipped: unowned SNAP page exists")
            return None
    page = SnapPanel(book)
    if not book.AddPage(page, "SNAP", False):
        page.dispose()
        page.Destroy()
        return None
    book.GetParent().Layout()
    return page


def remove_snap_tab(frame):
    from .snap_preferences import cleanup

    cleanup()
    if frame is None or not bool(frame) or frame.IsBeingDeleted():
        return
    book = find_appearance_notebook(frame)
    if book is None:
        return
    for i in range(book.GetPageCount() - 1, 2, -1):
        page = book.GetPage(i)
        if page.GetName() == OWNER:
            if hasattr(page, "dispose"):
                page.dispose()
            if book.GetSelection() == i:
                book.SetSelection(0)
            book.RemovePage(i)
            page.Destroy()
