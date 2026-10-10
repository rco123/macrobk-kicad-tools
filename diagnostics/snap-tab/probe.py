"""KiCad-process-only Appearance probe. No config writes or native setters.

Execute with runpy from KiCad console/Manager, then call start().
All GUI operations are scheduled on GUI thread by start/remove_snap_probe_tab.
No timers, worker, reparenting, native page edits, or guessed window IDs.
"""
import json
import traceback
from pathlib import Path

import pcbnew
import wx

ROOT = Path(__file__).resolve().parent
OWNER = 'MacroBK.diagnostics.snap-tab.v1'


def write(name, value):
    ROOT.joinpath(name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def identity(window):
    def read(method, default=None):
        try:
            return getattr(window, method)()
        except (AttributeError, RuntimeError):
            return default
    return {'python_class': type(window).__module__ + '.' + type(window).__name__,
            'native_class': str(read('GetClassName', 'not exposed')),
            'object': repr(window), 'id': read('GetId'), 'name': read('GetName'),
            'label': read('GetLabel'), 'title': read('GetTitle'),
            'size': list(read('GetSize', (0, 0))),
            'shown': read('IsShown'), 'being_deleted': read('IsBeingDeleted')}


def walk(root):
    yield root
    for child in root.GetChildren():
        yield from walk(child)


def require_gui():
    if not wx.IsMainThread():
        raise RuntimeError('GUI thread required')


def pages(book):
    return [{'index': i, 'text': book.GetPageText(i),
             'page': identity(book.GetPage(i))} for i in range(book.GetPageCount())]


def locate():
    require_gui()
    expected = [wx.GetTranslation(n) for n in ('Layers', 'Objects', 'Nets')]
    matches = []
    for frame in wx.GetTopLevelWindows():
        if frame.IsBeingDeleted() or not isinstance(frame, wx.Frame):
            continue
        # Confirm PCB Editor by live board path/title and page signature; reject fpedit.
        if 'PCB Editor' not in frame.GetTitle():
            continue
        for child in walk(frame):
            if isinstance(child, wx.Notebook) and child.GetPageCount() >= 3:
                if [child.GetPageText(i) for i in range(3)] == expected:
                    matches.append((frame, child))
    if len(matches) != 1:
        raise RuntimeError('Expected one PCB Appearance wx.Notebook; found {}'.format(len(matches)))
    return matches[0]


def inspect():
    require_gui()
    frame, book = locate()
    chain = []
    parent = book
    while parent is not None:
        chain.append(identity(parent))
        parent = parent.GetParent()
    manager = pcbnew.GetSettingsManager()
    result = {'version': pcbnew.Version(), 'frame': identity(frame),
              'notebook': identity(book), 'parent_chain': chain, 'pages': pages(book),
              'methods': {n: callable(getattr(book, n, None)) for n in
                          ('AddPage', 'InsertPage', 'RemovePage', 'DeletePage')},
              'settings_manager': {'class': type(manager).__name__,
                                   'GetAppSettings': callable(getattr(manager, 'GetAppSettings', None)),
                                   'GetPcbNewSettings': callable(getattr(frame, 'GetPcbNewSettings', None)),
                                   'GetMagneticItemsSettings': callable(getattr(frame, 'GetMagneticItemsSettings', None))},
              'magnetic_bindings': {n: hasattr(pcbnew, n) for n in
                                    ('PCBNEW_SETTINGS', 'MAGNETIC_SETTINGS', 'MAGNETIC_OPTIONS')}}
    tree = []
    for control in walk(book.GetParent()):
        row = identity(control)
        row['parent'] = identity(control.GetParent()) if control.GetParent() else None
        row['children'] = [identity(c) for c in control.GetChildren()]
        tree.append(row)
    write('hierarchy.json', tree)
    write('inspection.json', result)
    return result


def add_snap_probe_tab():
    require_gui()
    frame, book = locate()
    for i in range(book.GetPageCount()):
        page = book.GetPage(i)
        if page.GetName() == OWNER:
            if book.GetPageText(i) != 'SNAP':
                raise RuntimeError('Owned probe has unexpected label')
            return {'created': False, 'index': i, 'pages': pages(book)}
        if book.GetPageText(i) == 'SNAP':
            raise RuntimeError('Unowned SNAP page exists; will not change it')
    original = [book.GetPage(i) for i in range(3)]
    focus = wx.Window.FindFocus()
    selected = book.GetSelection()
    panel = wx.Panel(book, name=OWNER)
    sizer = wx.BoxSizer(wx.VERTICAL)
    title = wx.StaticText(panel, label='SNAP — MacroBK diagnostic probe')
    title.Wrap(max(100, book.GetClientSize().width - 24))
    sizer.Add(title, 0, wx.ALL, 12)
    label = wx.StaticText(panel, label='Test label\nRuntime snap getter is unverified.\nNo snap setting is changed.')
    label.Wrap(max(100, book.GetClientSize().width - 24))
    sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
    panel.SetSizer(sizer)

    def destroyed(event):
        if event.GetEventObject() is panel:
            try:
                write('destruction.json', {'owned_page_destroyed': True,
                                           'reason': 'explicit remove or parent destruction',
                                           'timer': False, 'frame_bindings': False})
            except OSError:
                pass
        event.Skip()

    panel.Bind(wx.EVT_WINDOW_DESTROY, destroyed)
    if not book.AddPage(panel, 'SNAP', False):
        panel.Destroy()
        raise RuntimeError('AddPage returned False')
    book.GetParent().Layout()
    assert all(book.GetPage(i) is original[i] or book.GetPage(i) == original[i] for i in range(3))
    assert book.GetSelection() == selected
    return {'created': True, 'index': book.GetPageCount() - 1, 'pages': pages(book),
            'original_pages_preserved': True,
            'immediate_focus_preserved': wx.Window.FindFocus() == focus}


def remove_on_gui():
    require_gui()
    frame, book = locate()
    removed = 0
    for i in range(book.GetPageCount() - 1, 2, -1):
        page = book.GetPage(i)
        if page.GetName() == OWNER:
            if book.GetSelection() == i:
                book.SetSelection(0)
            if not book.RemovePage(i):
                raise RuntimeError('RemovePage failed')
            page.Destroy()
            removed += 1
    book.GetParent().Layout()
    result = {'removed': removed, 'remaining_pages': pages(book)}
    write('removal.json', result)
    return result


def remove_snap_probe_tab():
    if wx.IsMainThread():
        return remove_on_gui()
    wx.CallAfter(remove_on_gui)
    return 'removal scheduled on GUI thread'


def capture_state(note='manual observation'):
    require_gui()
    frame, book = locate()
    focus = wx.Window.FindFocus()
    result = {'note': note, 'frame': identity(frame), 'notebook': identity(book),
              'pages': pages(book), 'selection': book.GetSelection(),
              'focus': identity(focus) if focus is not None else None,
              'owned_page_count': sum(book.GetPage(i).GetName() == OWNER
                                      for i in range(book.GetPageCount()))}
    path = ROOT / 'observations.json'
    records = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    records.append(result)
    write('observations.json', records)
    return result


def exercise_on_gui():
    """Reversible live tab/resize/reload/remove checks; does not close Editor."""
    require_gui()
    starting_probe = add_snap_probe_tab()
    frame, book = locate()
    selection = book.GetSelection()
    size = frame.GetSize()
    original = [(book.GetPage(i).GetId(), book.GetPageText(i)) for i in range(3)]
    checks = []
    try:
        for i in range(book.GetPageCount()):
            book.SetSelection(i)
            book.GetParent().Layout()
            checks.append({'tab': book.GetPageText(i), 'selected': book.GetSelection() == i,
                           'page_shown': book.GetPage(i).IsShown(),
                           'size': list(book.GetPage(i).GetSize())})
        frame.SetSize((max(800, size.width - 100), max(600, size.height - 80)))
        frame.Layout()
        book.GetParent().Layout()
        resized = capture_state('programmatic frame resize; visual clipping unverified')
    finally:
        frame.SetSize(size)
        frame.Layout()
        book.SetSelection(min(selection, book.GetPageCount() - 1))
    assert [(book.GetPage(i).GetId(), book.GetPageText(i)) for i in range(3)] == original
    # Reload module explicitly to prove owned-name lookup survives new globals.
    import runpy
    reloaded = runpy.run_path(str(ROOT / 'probe.py'))
    repeat = reloaded['add_snap_probe_tab']()
    assert not repeat['created']
    removal = remove_on_gui()
    assert removal['removed'] == 1 and book.GetPageCount() == 3
    second_removal = remove_on_gui()
    assert second_removal['removed'] == 0
    result = {'starting_probe': starting_probe, 'tab_checks': checks, 'resize': resized,
              'native_pages_preserved': True, 'reload_reused': repeat,
              'removal': removal, 'second_removal': second_removal,
              'final_page_count': book.GetPageCount(),
              'editor_close': 'NOT TESTED', 'manager_close': 'NOT TESTED',
              'theme_dpi_collapse': 'NOT TESTED', 'visual_layout': 'NOT TESTED'}
    write('live_ui_checks.json', result)
    print('SNAP tab/reload/remove checks saved; probe removed')
    return result


def exercise_ui():
    if wx.IsMainThread():
        return exercise_on_gui()
    wx.CallAfter(exercise_on_gui)
    return 'UI checks scheduled; original size restored and probe removed on completion'


def read_preferences_controls():
    """Read OPEN Preferences draft controls only; not committed runtime getters."""
    require_gui()
    rows = {}
    labels = ('Snap to pads:', 'Snap to tracks and vias:', 'Snap to graphics:')
    for root in wx.GetTopLevelWindows():
        for control in walk(root):
            if not isinstance(control, wx.StaticText):
                continue
            for key in labels:
                if control.GetLabel() != wx.GetTranslation(key):
                    continue
                siblings = list(control.GetParent().GetChildren())
                index = siblings.index(control)
                choice = siblings[index + 1] if index + 1 < len(siblings) else None
                if isinstance(choice, wx.Choice):
                    rows.setdefault(key, []).append({'choice': identity(choice),
                        'options': list(choice.GetStrings()), 'selection': choice.GetSelection(),
                        'display': choice.GetStringSelection(), 'scope': 'Preferences draft'})
    write('preferences_draft.json', rows)
    return rows


def run_on_gui():
    require_gui()
    try:
        inspection = inspect()
        first = add_snap_probe_tab()
        second = add_snap_probe_tab()
        frame, book = locate()
        # Leave selection unchanged. Human click/resize/theme tests are separate.
        result = {'inspection': inspection, 'first_add': first, 'repeat_add': second,
                  'duplicate_test': 'PASS' if first['created'] and not second['created'] else 'REUSED',
                  'ui_selection_resize_theme': 'NOT TESTED', 'editor_close': 'NOT TESTED',
                  'runtime_getter': 'NOT VERIFIED', 'runtime_setter': 'NOT ATTEMPTED',
                  'preferences_sync': 'NOT TESTED', 'timer': False}
        write('live_result.json', result)
        print('SNAP probe added/reused; diagnostics/snap-tab/live_result.json saved')
    except Exception:
        write('live_error.json', {'error': traceback.format_exc()})
        raise


def start():
    if wx.GetApp() is None:
        raise RuntimeError('Execute inside live KiCad Python, not external Python')
    if wx.IsMainThread():
        return run_on_gui()
    wx.CallAfter(run_on_gui)
    return 'probe scheduled on GUI thread'
