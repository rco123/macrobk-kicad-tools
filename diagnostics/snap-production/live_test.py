"""Compatibility entry point for previously saved Action script paths."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(
        str(Path(__file__).resolve().parents[2] / 'examples' / 'snap_settings.py'),
        run_name='__main__',
    )
