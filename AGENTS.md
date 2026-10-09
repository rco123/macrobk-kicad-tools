# MacroBK KiCad PCB Plugin workspace

- Perform all code changes, tests, and Git operations in this directory:
  `C:\Users\sgkim\Documents\KiCad\9.0\scripting\plugins\macrobk_drc_bridge`.
- Do not use the former E: project as a work target.
- Preserve this directory's existing `config.json` user settings. Do not replace
  them with another project's configuration; tests must use temporary files.
- PCB Editor only; preserve Phone all-actions matching and the worker/helper engine.
- Run tests from this root with KiCad Python:
  `"C:\Program Files\KiCad\9.0\bin\python.exe" -B -m unittest discover -s tests -p "test_*.py" -v`
