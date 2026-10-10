# MacroBK KiCad Tools workspace

- Make code changes and Git operations from this repository root. Use a separate
  branch for cleanup; do not change main before the user approves a merge.
- The existing Windows installation path is
  `C:\Users\sgkim\Documents\KiCad\9.0\scripting\plugins\macrobk_drc_bridge`.
  Do not use the former E: project as an installation target.
- Preserve the existing `config.json` byte-for-byte unless the user explicitly
  requests a configuration change. Tests must use temporary config/log/settings.
- PCB Editor only; preserve Phone all-actions matching, public Action helpers,
  and the worker/GUI helper engine. Apply live source changes by restarting PCB
  Editor, not by refreshing or reloading running workers.
- Keep usage documentation in README.md. Do not commit logs, captured evidence,
  old test output, or downloaded upstream source copies.
- Full integration command from the repository root, with KiCad Python:
  `"C:\Program Files\KiCad\9.0\bin\python.exe" -B -m unittest discover -s tests -p "test_*.py" -v`
- Portable settings/sender tests run with ordinary Python. Missing KiCad/wx
  integration dependencies must be reported as skipped, not a live-board pass.
