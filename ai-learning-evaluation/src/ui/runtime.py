"""Lightweight startup checks, diagnostics and visible GUI error reporting."""
import json
import platform
import re
import sys
import traceback
from pathlib import Path


def _setup_environment():
    import os
    if sys.platform == 'win32':
        prefix = Path(sys.prefix)
        # Conda configures Tcl after its DLL search paths are activated. Its
        # default discovery is correct; overriding it makes init.tcl unusable.
        if (prefix / 'conda-meta').exists():
            return
        for base in (prefix / 'tcl', prefix / 'Library' / 'lib'):
            for variable, directory in (('TCL_LIBRARY', 'tcl8.6'), ('TK_LIBRARY', 'tk8.6')):
                candidate = base / directory
                if candidate.exists():
                    os.environ.setdefault(variable, str(candidate))


def check_tk_version(version, system=None):
    system = system or platform.system()
    numbers = tuple(int(n) for n in re.findall(r'\d+', version)[:3])
    if system == 'Darwin' and numbers < (8, 6, 11):
        raise RuntimeError(
            f'This Python uses Tk {version}, which is too old for this macOS application. '
            'Install Python 3.13 from python.org with its bundled Tcl/Tk, then run '
            'python app.py using that Python. An existing .venv keeps its old Python; '
            'use the new .venv-mac environment described in TEAM_TESTING.md. '
            'Do not suppress the Tk deprecation warning.')


def runtime_details(root):
    return {'python': sys.version.split()[0], 'executable': sys.executable,
            'system': platform.system(), 'os_version': platform.release(),
            'tcl': str(root.tk.call('info', 'patchlevel')),
            'tk': str(root.tk.call('package', 'require', 'Tk')),
            'window_system': str(root.tk.call('tk', 'windowingsystem'))}


def launch(diagnose=False):
    root = app = None
    # On Conda for Windows, importing a compiled dependency first registers
    # the environment DLL directories needed by Tcl/Tk as well.
    if sys.platform == 'win32':
        import pandas  # noqa: F401
    _setup_environment()
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        details = runtime_details(root)
        print(json.dumps(details, indent=2))
        check_tk_version(details['tk'], details['system'])
        if diagnose:
            root.destroy()
            return 0

        def callback_error(kind, value, tb):
            traceback.print_exception(kind, value, tb)
            messagebox.showerror('Application error',
                f'{kind.__name__}: {value}\n\nPlease send the terminal error and '
                'the output of python app.py --diagnose to the team.', parent=root)
        root.report_callback_exception = callback_error
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)
        from src.ui.desktop import DesktopApp
        app = DesktopApp(root)
        root.update_idletasks()
        root.deiconify()
        root.mainloop()
        return 0
    except Exception as exc:
        traceback.print_exc()
        if app is not None:
            app.pool.shutdown(wait=False, cancel_futures=True)
        if root is not None:
            try:
                from tkinter import messagebox
                if not diagnose:
                    messagebox.showerror('Unable to start Insight Hub',
                        f'{exc}\n\nRun python app.py --diagnose from a terminal for runtime details.', parent=root)
            finally:
                root.destroy()
        return 1


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Learning Futures evaluation application')
    parser.add_argument('--diagnose', action='store_true', help='Check Python and Tk without loading survey data')
    args = parser.parse_args()
    return launch(args.diagnose)
