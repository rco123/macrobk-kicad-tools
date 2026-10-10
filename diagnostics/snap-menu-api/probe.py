"""Live Preferences round trip using already-loaded MacroBK helpers only.

Run start() from MacroBK Manager (without Save). No config writes, keys,
coordinates, custom native bindings, production edits, or Appearance changes.
"""
import json
import sys
import traceback
from pathlib import Path
import wx

ROOT = Path(__file__).resolve().parent
APP_KEY = '_macrobk_snap_menu_diagnostic'


def helpers():
    modules = [m for name, m in sys.modules.items()
               if name.endswith('.kicad_controls') and m is not None
               and callable(getattr(m, 'open_menu', None))]
    if len(modules) != 1:
        raise RuntimeError('Expected one already-loaded MacroBK kicad_controls module')
    return modules[0]


class Probe:
    def __init__(self, restore_only=False):
        self.kc = helpers()
        self.running = True
        self.timers = []
        self.phase = 0
        self.polls = 0
        self.recovering = restore_only
        self.result = {'verdict': 'RUNNING', 'runtime_snap': 'NOT TESTED',
                       'helpers': ['open_menu', 'find_controls', 'iter_controls',
                                   'get_control_info', 'get_control_value',
                                   'set_control_value', '_command_ok_button'],
                       'production_modified': False, 'stages': []}
        if restore_only:
            old = json.loads((ROOT / 'result.json').read_text(encoding='utf-8'))
            self.result['original'] = old['original']
            self.phase = 1
        self.save()

    def save(self):
        (ROOT / 'result.json').write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding='utf-8')

    def later(self, method, delay=300):
        self.timers = [t for t in self.timers if t.IsRunning()]
        self.timers.append(wx.CallLater(delay, method))

    def prefs(self):
        windows = [w for w in wx.GetTopLevelWindows() if isinstance(w, wx.Dialog)
                   and not w.IsBeingDeleted() and w.IsShown()
                   and 'preferences' in w.GetTitle().lower()]
        if len(windows) > 1:
            raise RuntimeError('Ambiguous Preferences dialogs')
        return windows[0] if windows else None

    def open(self):
        try:
            if self.prefs() is not None:
                raise RuntimeError('Preferences already open; refusing to accept unrelated drafts')
            self.polls = 0
            # Arm BEFORE menu dispatch: native ShowModal runs a nested event loop.
            self.later(self.step)
            if not self.kc.open_menu('Preferences -> Preferences'):
                raise RuntimeError('Existing open_menu could not dispatch Preferences')
        except Exception:
            self.fail()

    def choose_page(self, dialog):
        books = self.kc.find_controls(dialog, control_type=wx.Treebook)
        if len(books) != 1:
            raise RuntimeError('Expected one actual Preferences wx.Treebook')
        book = books[0]
        page_rows = []
        matches = []
        for i in range(book.GetPageCount()):
            parent = book.GetPageParent(i)
            row = {'index': i, 'text': book.GetPageText(i), 'parent': parent,
                   'parent_text': book.GetPageText(parent) if parent >= 0 else None}
            page_rows.append(row)
            if self.kc.norm_label(row['text']) == self.kc.norm_label(wx.GetTranslation('Editing Options')):
                ancestors = []
                cursor = parent
                while cursor >= 0:
                    ancestors.append(self.kc.norm_label(book.GetPageText(cursor)))
                    cursor = book.GetPageParent(cursor)
                if self.kc.norm_label(wx.GetTranslation('PCB Editor')) in ancestors:
                    matches.append(i)
        self.result['preferences_pages'] = page_rows
        if len(matches) != 1:
            raise RuntimeError('Expected one PCB Editor / Editing Options page')
        book.SetSelection(matches[0])
        return book.GetPage(matches[0])

    def choice(self, dialog):
        page = self.choose_page(dialog)
        labels = self.kc.find_controls(page, control_type=wx.StaticText,
                                       label=wx.GetTranslation('Snap to pads:'))
        if len(labels) != 1:
            raise RuntimeError('Snap to pads label was not unique')
        label = labels[0]
        siblings = list(label.GetParent().GetChildren())
        position = siblings.index(label)
        control = siblings[position + 1] if position + 1 < len(siblings) else None
        expected = [wx.GetTranslation(x) for x in ('Never', 'When routing tracks', 'Always')]
        if not isinstance(control, wx.Choice) or list(control.GetStrings()) != expected:
            raise RuntimeError('Adjacent control is not the verified native pads Choice')
        return control

    def sample(self, control):
        return dict(self.kc.get_control_info(control),
                    selection=control.GetSelection(),
                    string_selection=self.kc.get_control_value(control),
                    choices=list(control.GetStrings()),
                    native_class=control.GetClassName())

    def step(self):
        try:
            dialog = self.prefs()
            if dialog is None:
                self.polls += 1
                if self.polls >= 50:
                    raise RuntimeError('Preferences did not open within bounded wait')
                self.later(self.step, 200)
                return
            control = self.choice(dialog)
            sample = self.sample(control)
            self.result['stages'].append({'phase': self.phase, 'read': sample})
            if self.phase == 0:
                self.result['original'] = sample['string_selection']
                self.result['initial_control'] = sample
                self.result['requested'] = control.GetString(0 if sample['selection'] == 2 else 2)
                self.kc.set_control_value(control, self.result['requested'])
                self.result['draft_after_set'] = self.sample(control)
                self.result['restore_required'] = True
            elif self.phase == 1:
                self.result['after_reopen'] = sample['string_selection']
                self.result['changed_reopen_pass'] = (not self.recovering and
                    sample['string_selection'] == self.result['requested'])
                self.kc.set_control_value(control, self.result['original'])
                self.result['restoration_draft'] = self.sample(control)
            elif self.phase == 2:
                self.result['restored_reopen'] = sample['string_selection']
                self.result['restore_pass'] = sample['string_selection'] == self.result['original']
                self.result['restore_required'] = not self.result['restore_pass']
                if not self.result['restore_pass']:
                    self.save()
                    raise RuntimeError('Original value was not restored; attempting bounded recovery')
            self.save()  # Original survives exceptions, process exit, and reload.
            self.kc._command_ok_button(dialog)
            self.result['stages'][-1]['native_ok_dispatched'] = True
            self.save()
            if self.phase < 2:
                self.phase += 1
                self.later(self.open, 500)
            else:
                self.result['verdict'] = ('PASS' if self.result.get('changed_reopen_pass')
                                          and self.result.get('restore_pass') else 'READ ONLY')
                self.finish()
        except Exception:
            self.fail()

    def finish(self):
        self.running = False
        for timer in self.timers:
            timer.Stop()
        self.timers.clear()
        self.save()
        print('Snap to pads result:', self.result['verdict'], '; restore:', self.result.get('restore_pass'))

    def fail(self):
        self.result.setdefault('errors', []).append(traceback.format_exc())
        # If draft changed before OK, put original back before accepting dialog.
        if self.result.get('restore_required') and not self.recovering:
            try:
                dialog = self.prefs()
                if dialog is not None:
                    control = self.choice(dialog)
                    self.kc.set_control_value(control, self.result['original'])
                    self.kc._command_ok_button(dialog)
                    self.recovering = True
                    self.phase = 2
                    self.save()
                    self.later(self.open, 500)
                    return
            except Exception:
                self.result['errors'].append(traceback.format_exc())
        self.result['verdict'] = 'FAIL'
        self.finish()


def start(restore_only=False):
    app = wx.GetApp()
    if app is None:
        raise RuntimeError('Execute inside live KiCad Python')
    def launch():
        active = getattr(app, APP_KEY, None)
        if active is not None and active.running:
            raise RuntimeError('Snap menu probe already running')
        probe = Probe(restore_only)
        setattr(app, APP_KEY, probe)
        probe.open()
    wx.CallAfter(launch)
    return 'Snap to pads round trip scheduled; original value will be restored'
