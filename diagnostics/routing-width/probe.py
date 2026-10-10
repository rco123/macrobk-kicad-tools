"""Isolated width experiments. No imports or edits to production plugin code.

Load in KiCad's scripting console using runpy.run_path(absolute_path).
Call run_case('B', .4, source='console') on the GUI thread, or arm_case()
then return to PCB canvas before its timer fires. D intentionally rebuilds view.
No native router notification is simulated. No config or board file is saved.
"""
import json
import math
from pathlib import Path

import pcbnew


def snapshot(board):
    settings = board.GetDesignSettings()
    return {
        'current_mm': pcbnew.ToMM(settings.GetCurrentTrackWidth()),
        'custom_mm': pcbnew.ToMM(settings.GetCustomTrackWidth()),
        'custom_mode': settings.UseCustomTrackViaSize(),
        'index': settings.GetTrackWidthIndex(),
        'presets_iu': list(settings.m_TrackWidthList),
        'via_iu': [settings.GetCurrentViaSize(), settings.GetCurrentViaDrill()],
        'committed_widths_iu': sorted(int(t.GetWidth()) for t in board.GetTracks()),
    }


def run_case(case, width_mm, *, board=None, frame=None, source='unspecified'):
    """A setter; B mode; C UI; D rebuild; E index; F/G wx; H pending.

    E selects the existing index AFTER B, deliberately testing custom-mode loss.
    F/G require a verified live PCB frame supplied by caller; no guessed frames.
    """
    if case not in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'):
        raise ValueError('unknown case')
    width_mm = float(width_mm)
    if not math.isfinite(width_mm) or width_mm <= 0:
        raise ValueError('positive finite width required')
    if case in ('F', 'G') and frame is None:
        raise ValueError('verified PCB frame required')
    if board is None:
        board = pcbnew.GetBoard()
        if board is None:
            raise RuntimeError('no live PCB board')
        import wx
        if not wx.IsMainThread():
            raise RuntimeError('run on KiCad GUI thread')
    settings = board.GetDesignSettings()
    before = snapshot(board)
    settings.SetCustomTrackWidth(pcbnew.FromMM(width_mm))
    calls = ['SetCustomTrackWidth']
    if case != 'A':
        settings.SetCustomViaSize(before['via_iu'][0])
        settings.SetCustomViaDrill(before['via_iu'][1])
        settings.UseCustomTrackViaSize(True)
        calls += ['SetCustomViaSize', 'SetCustomViaDrill', 'UseCustomTrackViaSize(True)']
    if case == 'C':
        pcbnew.UpdateUserInterface()
        calls.append('UpdateUserInterface')
    elif case == 'D':
        pcbnew.Refresh()
        calls.append('Refresh')
    elif case == 'E':
        settings.SetTrackWidthIndex(before['index'])
        calls.append('SetTrackWidthIndex(existing index)')
    elif case in ('F', 'G'):
        getattr(frame, 'Update' if case == 'F' else 'Refresh')()
        calls.append('frame.Update' if case == 'F' else 'frame.Refresh')
    elif case == 'H':
        import wx
        wx.GetApp().ProcessPendingEvents()
        calls.append('ProcessPendingEvents')
    result = {'case': case, 'source': source, 'calls': calls,
              'before': before, 'after': snapshot(board),
              'preview': 'NOT OBSERVED', 'mouse_preview': 'NOT OBSERVED',
              'X': 'NOT TESTED', 'next_route': 'NOT TESTED',
              'toolbar': 'NOT OBSERVED', 'focus': 'NOT OBSERVED'}
    if source != 'detached-board':
        import wx
        focus = wx.Window.FindFocus()
        result['focus'] = None if focus is None else {
            'class': focus.GetClassName(), 'name': focus.GetName(), 'id': focus.GetId()}
    print(json.dumps(result, ensure_ascii=False))
    return result


def arm_case(case, width_mm, delay_ms=10000, *, frame=None):
    """One-shot console experiment; keep returned timer to Stop() if needed.

    Does not prove Phone/keyboard triggering. Return canvas focus and start route
    before timeout. No recurring worker or trigger configuration is installed.
    """
    import wx
    return wx.CallLater(delay_ms, run_case, case, width_mm,
                        frame=frame, source='console-delay')


def detached_checks():
    def fixture():
        board = pcbnew.BOARD()
        settings = board.GetDesignSettings()
        settings.m_TrackWidthList.append(0)
        settings.m_TrackWidthList.append(pcbnew.FromMM(.25))
        settings.SetTrackWidthIndex(1)
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pcbnew.VECTOR2I(0, 0))
        track.SetEnd(pcbnew.VECTOR2I(1000000, 0))
        track.SetWidth(pcbnew.FromMM(.25))
        board.Add(track)
        return board

    results = []
    for case in ('A', 'B', 'E'):
        board = fixture()
        result = run_case(case, .4, board=board, source='detached-board')
        assert result['after']['presets_iu'] == result['before']['presets_iu']
        assert result['after']['committed_widths_iu'] == result['before']['committed_widths_iu']
        if case == 'A':
            assert result['after']['current_mm'] == result['before']['current_mm']
        if case == 'B':
            assert result['after']['current_mm'] == .4
            assert result['after']['via_iu'] == result['before']['via_iu']
        if case == 'E':
            assert result['after']['custom_mode'] is False
        results.append(result)
    board = fixture()
    for width in (.4, .75, .3):
        result = run_case('B', width, board=board, source='detached-board')
        assert result['after']['current_mm'] == width
        assert result['after']['presets_iu'] == result['before']['presets_iu']
        results.append(result)
    names = ('TOOL_MANAGER', 'PCB_ACTIONS', 'ROUTER_TOOL', 'TOOL_EVENT',
             'GetToolManager', 'RunAction', 'GetPcbEditFrame')
    output = {'version': pcbnew.Version(),
              'module_bindings': {n: hasattr(pcbnew, n) for n in names},
              'cases': results, 'scope': 'detached BOARD; no live router/window'}
    Path(__file__).with_name('detached_results.json').write_text(
        json.dumps(output, indent=2), encoding='utf-8')


if __name__ == '__main__':
    detached_checks()
